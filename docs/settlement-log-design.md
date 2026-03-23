# 结算日志系统设计

## 目标

为当前工作流增加一套可持久化的“结算日志系统”，记录每一次真正落地到 world-state 的结算过程。

这里的“结算日志”不是普通调试日志，而是面向以下场景的结构化事件记录：

- DM 回看上一轮到底改了哪些状态
- 对比 resolver 合并前后的差异
- 排查“为什么这次伤害还是落地了”
- 为未来的回放、撤销、导出 recap 提供数据基础

该系统应优先服务当前主流程：

`planner -> task_approval -> executor -> window_review -> resolver -> commiter`

## 为什么现在要做

当前项目已经具备：

- 结构化 `TaskExecution`
- 结构化 `ExecutionResult`
- 结构化 `ResolutionWindow` / `ResolutionResult`
- 在 `commiter` 节点统一写回字段级变更

这意味着系统已经天然具备“记录一次结算”的关键边界。

但目前缺少一个稳定的、可审计的落地层：

- `Executor` 的产出会打印到控制台，但不会作为历史保留下来
- `Resolver` 的取舍结果没有持久化审计轨迹
- `WriteFieldsTool` 会直接修改 KV，但没有形成标准化提交记录
- `KVStateStore` 只保存“当前状态”，不保存“如何变成现在这样”

所以现在最合适的做法，不是继续增加临时打印，而是正式引入“提交级事件日志”。

## 设计原则

- 以“提交事件”为中心，而不是以低层 KV 操作为中心
- 先记录“真正写回 world-state 的结果”，再扩展到完整回放
- V1 优先可读、可查、可审计，不追求一步到位的 event sourcing
- 日志记录尽量不改变现有 Planner / Executor / Resolver 职责边界
- 失败和跳过也要记录，避免只记录成功路径

## 非目标

V1 不解决以下问题：

- 不把整个 world-state 重构成 event sourcing
- 不要求每次 `store.set()` 都自动生成底层日志
- 不立刻提供完整“任意时点状态重建”
- 不在 V1 直接实现撤销 / 重放执行，只为其预留数据结构
- 不替代现有终端调试输出

## 推荐挂载点

推荐把结算日志系统挂在 `commiter` 节点，而不是直接塞进 `KVStateStore`。

原因：

1. `commiter` 拥有最完整的业务上下文

- 当前任务 `TaskExecution`
- 当前执行结果 `ExecutionResult`
- 如果存在窗口，则还能拿到 `ResolutionWindow` 和 `ResolutionResult`
- 最终准备写回的 `payload_changes`

2. `commiter` 是“是否真正生效”的边界

- `executor` 产出的变更只是候选
- `resolver` 产出的变更是裁定结果
- 只有 `commiter` 才知道哪些变更最终被提交、跳过、失败

3. 更适合未来做回放 / 撤销

- 日志记录的是“业务提交”
- 而不是一堆不带上下文的 `store.set(key, value)`

因此 V1 推荐采用：

- `commiter` 负责组装日志事件
- 独立的 `SettlementLogStore` 负责持久化
- `KVStateStore` 保持“当前状态存储”的单一职责

## 系统边界

### 输入来源

日志系统从以下对象采集信息：

- `TaskExecution`
- `ExecutionResult`
- `ResolutionWindow`
- `ResolutionResult`
- `payload_changes`
- `write_fields` 工具返回结果
- world-state 写回前后的字段值

### 输出目标

V1 输出到磁盘结构化日志文件，推荐 JSONL。

推荐目录：

`data/settlement_logs/`

推荐文件：

- `data/settlement_logs/session-YYYYMMDD.jsonl`
- 或 `data/settlement_logs/<thread_id>.jsonl`

V1 优先选 `JSONL`，因为：

- 追加写入简单
- 单条事件天然独立
- CLI 检索方便
- 以后导出 Markdown recap 也容易

## 日志粒度

V1 只记录一种核心事件：

- `settlement_committed`

但单条日志内部需要覆盖三类结果：

1. 成功写回的字段
2. 被跳过的字段
3. 写回失败的字段

换句话说，V1 不要求拆成多种事件流；先保证“一次 commiter 执行，对应一条完整提交记录”。

## 数据模型

推荐新增三个内部概念。

### 1. `ChangeCommitRecord`

描述单个字段变更在提交阶段的最终命运。

建议字段：

```json
{
  "path": "Aldera.combat.HP",
  "key": "Aldera.combat",
  "field": "HP",
  "operation": "MOD",
  "source": "resolver:window_001",
  "old_value_claimed": "44/44",
  "old_value_actual": "44/44",
  "new_value": "33/44",
  "status": "applied",
  "reason": ""
}
```

字段说明：

- `old_value_claimed`: 上游 agent / resolver 声称的旧值
- `old_value_actual`: commiter 写回前从 store 真实读到的旧值
- `status`: `applied` / `skipped` / `failed`
- `reason`: 跳过或失败原因

### 2. `SettlementSummary`

描述本次提交的整体概况。

建议字段：

```json
{
  "applied_count": 2,
  "skipped_count": 1,
  "failed_count": 0,
  "mode": "resolved_window"
}
```
 
`mode` 建议值：

- `direct_execution`: 直接提交 `ExecutionResult`
- `resolved_window`: 提交 `ResolutionResult.final_field_changes`

### 3. `SettlementLogEntry`

这是最终写入 JSONL 的顶层对象。

建议 schema：

```json
{
  "event_id": "settle_20260321_0001",
  "event_type": "settlement_committed",
  "timestamp": "2026-03-21T14:23:11+08:00",
  "thread_id": "demo-thread",
  "mode": "resolved_window",
  "task": {
    "task_id": "task_magic_missile",
    "description": "马利克对艾尔德拉施放魔法飞弹",
    "actor": "Malik",
    "target": "Aldera",
    "source": "dm",
    "task_category": "normal"
  },
  "execution": {
    "success": true,
    "narration": "魔法飞弹造成 11 点力场伤害。"
  },
  "window": {
    "window_id": "window_001",
    "root_task_id": "task_magic_missile",
    "root_description": "马利克对艾尔德拉施放魔法飞弹",
    "run_count": 2
  },
  "resolution": {
    "window_id": "window_001",
    "resolution_summary": "resolver 对同窗口结果完成合并。",
    "discarded_count": 1
  },
  "summary": {
    "applied_count": 2,
    "skipped_count": 0,
    "failed_count": 0,
    "mode": "resolved_window"
  },
  "changes": [
    {
      "path": "Aldera.combat.HP",
      "key": "Aldera.combat",
      "field": "HP",
      "operation": "MOD",
      "source": "resolver:window_001",
      "old_value_claimed": "44/44",
      "old_value_actual": "44/44",
      "new_value": "33/44",
      "status": "applied",
      "reason": ""
    }
  ]
}
```

## 最小实现范围

V1 推荐只落下面这些字段：

- 顶层事件元信息
- task 摘要
- execution narration 摘要
- window / resolution 摘要
- 最终 `changes`
- applied / skipped / failed 统计

V1 暂时不强制记录：

- 完整 `TaskExecution.context`
- 完整 `ResolutionWindow.runs`
- 完整 `shared_context`
- 完整控制台输出

原因是这些字段 token 和体积都较大，且容易把日志变成“冗余快照仓库”。

## 写入时机

日志写入应发生在 `commiter` 内部，并遵循以下顺序：

1. 组装候选 `payload_changes`
2. 逐条读取当前 store 中的实际旧值
3. 执行 `write_fields`
4. 根据执行结果标记每条 change 的状态
5. 生成 `SettlementLogEntry`
6. 持久化日志

注意：

- 日志写入应在“本次提交流程收尾前”完成
- 即使 `payload_changes` 为空，也要写入一条日志，标明 `applied_count = 0`
- 如果 `write_fields` 抛异常，也应尽量写入一条失败日志

## 为什么不直接复用 `write_fields` 输出字符串

`WriteFieldsTool` 当前返回的是人类可读字符串，例如：

```text
[成功] 应用了 1/1 个字段变更:
✓ Aldera.combat.HP: 44/44 → 33/44
```

这适合终端展示，但不适合作为日志主数据源，原因是：

- 解析脆弱
- 无法稳定承载失败原因
- 丢失 task / window / resolver 上下文

因此 V1 应把 `write_fields` 继续视为“执行器”，而不是“日志源”。

## 推荐实现结构

建议新增模块：

`src/logging/settlement.py`

或如果不想和 Python 标准库 `logging` 命名混淆，可用：

`src/audit/settlement.py`

推荐包含：

- `ChangeCommitRecord`
- `SettlementSummary`
- `SettlementLogEntry`
- `SettlementLogStore`
- `build_settlement_log_entry(...)`

### `SettlementLogStore`

职责：

- 负责确定日志文件路径
- 负责追加写入 JSONL
- 不参与业务判断

建议接口：

```python
class SettlementLogStore:
    def append(self, entry: SettlementLogEntry) -> None:
        ...
```

### `build_settlement_log_entry(...)`

职责：

- 从 workflow state 和提交结果构造标准日志对象
- 统一填充 applied / skipped / failed
- 屏蔽 commiter 中的重复拼装逻辑

## 与现有代码的集成方式

### 1. `AppConfig`

建议增加：

- `settlement_log_dir: str = "data/settlement_logs"`
- `enable_settlement_log: bool = True`

### 2. `create_workflow()`

建议在 workflow 初始化时创建日志存储实例，并传给 `create_commiter_node(...)`。

现状：

- `create_commiter_node(write_fields_tool)`

建议改为：

- `create_commiter_node(write_fields_tool, settlement_log_store)`

### 3. `commiter`

`commiter` 需要补三件事：

- 不再只关心“写了几个字段”
- 要记录每个字段的提交状态
- 在 direct / resolved 两种模式都产生日志

### 4. `AgentState`

V1 不强制新增状态字段。

因为：

- 绝大多数日志信息在 `commiter` 时已经可拿到
- 日志更像 side effect，不必强行塞回 LangGraph state

如果后续需要在 CLI 内展示“最近一次提交日志摘要”，再考虑给 state 增加：

- `last_settlement_log_id`

## direct 和 resolved 两种模式的处理

### direct_execution

来源：

- `pending_resolution is None`
- 提交对象来自 `ExecutionResult.field_changes`

日志里应记录：

- 当前 `task`
- `execution.success`
- `execution.narration`
- `window = null`
- `resolution = null`

### resolved_window

来源：

- `pending_resolution is not None`
- 提交对象来自 `ResolutionResult.final_field_changes`

日志里应记录：

- 当前 `task`
- 最近一次 `ExecutionResult`
- 当前 `active_window` 摘要
- `ResolutionResult` 摘要
- `discarded_field_changes` 数量

注意：

V1 推荐只在日志中保存 `discarded_count`，而不是整份 discarded 列表；否则容易过胖。

## 跳过和失败的定义

V1 建议统一如下：

### `applied`

字段通过校验，并已成功写入 store。

### `skipped`

字段未尝试写入，常见原因：

- path 不是字段级路径
- 基础 key 不存在
- 当前模式不允许该类型写入

### `failed`

字段已尝试写入，但执行时抛异常。

这三种状态必须体现在日志里，不能只统计成功数。

## 文件格式建议

推荐单行一条 JSON：

```json
{"event_id":"settle_20260321_0001","event_type":"settlement_committed", ...}
```

不推荐 V1 直接写整份数组文件，原因：

- 追加不方便
- 容易因为一次中断损坏整个文件
- 不适合 CLI 实时 tail

## CLI 预留能力

这次 spec 不要求立即实现 CLI，但建议从一开始就为以下命令预留：

- `python test.py logs latest`
- `python test.py logs tail`
- `python test.py logs show <event_id>`

因此日志 schema 里必须有稳定的：

- `event_id`
- `timestamp`
- `thread_id`

## 测试建议

V1 至少增加以下测试：

1. direct 模式下成功提交时生成日志
2. resolved 模式下成功提交时生成日志
3. `payload_changes` 为空时仍生成日志
4. path 非法导致 skipped 时能记录原因
5. `write_fields` 异常时能生成失败日志

推荐新增：

- `tests/unit/test_settlement_log.py`

## 分阶段实施建议

### Phase 1

先做最小可用：

- 新增日志数据模型
- 新增 JSONL 持久化
- 在 `commiter` 写入日志
- direct / resolved 双路径接入

### Phase 2

增强可读性：

- CLI 查看最新日志
- 支持按 `event_id` 查询
- 支持导出 Markdown recap

### Phase 3

增强可操作性：

- 从日志反推上一次提交的反向 patch
- 基于日志做撤销
- 基于日志做窗口级回放

## Open Questions

### 1. 日志是否要记录完整上下文？

建议 V1 不记录完整 `task.context`，只记录摘要字段。否则日志会迅速膨胀。

### 2. 日志文件按日期切还是按 thread 切？

如果当前主要是单人本地调试，按日期更简单。
如果后续强调多线程会话回看，按 `thread_id` 更有用。

建议 V1：

- 文件按日期
- 事件内保留 `thread_id`

### 3. 是否要把 discarded changes 也完整写进去？

建议 V1 只写数量摘要，Phase 2 再决定是否展开。

## 推荐结论

结算日志系统的第一版应定义为：

“由 `commiter` 在每次 world-state 真正写回时，生成一条结构化提交事件，并以 JSONL 形式持久化到 `data/settlement_logs/`。”

这条路线的优点是：

- 最贴合当前架构
- 对现有 Agent 侵入最小
- 对未来的回放、撤销、recap 都有明确演进空间

它不是把项目立刻改造成 event-sourcing，而是先补上“结算可审计”这块最关键的基础设施。
