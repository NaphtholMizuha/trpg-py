# Resolver Window 收集设计

## 目标

这份文档只回答一个问题：

如何把多次 `executor` 的结果，收集成一个可交给 `resolver` 的 `ResolutionWindow`。

这里先不定义 `ResolverAgent` 的 prompt 细节，也不直接改写当前工作流实现，而是先明确最小可行的数据流。

## 设计原则

- 尽量复用现有 `planner -> task_approval -> executor -> commiter` 骨架
- 在 `commiter` 真正写回之前，给 DM 一个“是否仍属于同一结算窗口”的判断机会
- 先让 DM 显式决定是否追加同窗口动作，不尝试自动猜测所有 reaction
- `window` 只收集已经执行过的 `ExecutionResult`，不混入未执行任务
- `resolver` 只消费关闭后的 window；打开中的 window 不允许写回 world-state

## 当前工作流与问题

当前流程是：

1. `planner`
2. `task_approval`
3. `executor`
4. `commiter`
5. 回到 `planner`

问题在于：

- `executor` 一执行完就进入 `commiter`
- `commiter` 默认立即写入 `field_changes`
- 这样无法在写回前缓存“主动作 -> 反应 -> 反制 -> 再反制”这类同窗口链条

所以 window 收集的本质，是在 `executor` 与 `commiter` 之间插入一个“待提交缓存层”。

## 核心思路

引入一个运行时中的 `active_window: ResolutionWindow | None`。

V1 直接维护 `ResolutionWindow` 本身，同时把它作为：

- workflow 内的收集中窗口
- resolver 的输入对象

这样做的原因是：

- 当前项目阶段更需要先跑通 window 机制
- `ResolutionWindow` 现在已经足够贴近“收集中的窗口”语义
- 不必为了未来可能出现的流程态字段，先增加一层抽象

`active_window` 的基本语义是：

- 当它为空时，表示当前没有打开的结算窗口
- 当它存在且 `status == open` 时，表示正在收集同窗口内的多个 run
- 当 DM 确认不再追加动作时，把它标记为 `ready`
- 只有 `ready` 的 window 才会进入 `resolver`
- `resolver` 产出 `ResolutionResult` 后，再进入 `commiter`

也就是说，`commiter` 不再直接消费 `ExecutionResult`，而是消费：

- 无 window 模式下的直接结果，或
- 有 window 模式下经 `resolver` 合并后的 `final_field_changes`

## 为什么 V1 先不拆出单独的运行时结构

这份文档当前不再引入 `ActiveResolutionWindowState`。

原因是：

- 目前运行时收集字段和 `ResolutionWindow` 基本一致
- 如果现在强行拆层，复杂度会先于收益出现
- 先让同窗口收集、关闭、resolver 合并这条链路跑通，更符合当前阶段目标

如果后续 `window_review` 真的长出大量流程态字段，例如：

- 只属于 workflow 的中断状态
- review 次数
- UI 辅助信息

那时再把 `active_window` 拆成独立运行时结构会更合适。

## 建议增加的运行时状态

可以先在 `AgentState` 中增加以下字段：

```python
active_window: ResolutionWindow | None
pending_resolution: ResolutionResult | None
window_counter: int
```

含义如下：

- `active_window`: 当前正在收集的结算窗口
- `pending_resolution`: resolver 已输出、等待 commiter 写回的合并结果
- `window_counter`: 生成 `window_id`，避免重复

如果希望最小改动，也可以只加前两个字段，`window_id` 用时间戳或 uuid 生成。

## Window 生命周期

### 1. 打开 Window

打开时机：

- 当前没有 `active_window`
- `executor` 刚完成一个任务
- 系统准备询问 DM：是否存在“优先级更高且仍属于同一结算窗口”的动作

此时用当前的 `TaskExecution + ExecutionResult` 初始化 `ResolutionWindow`：

- `window_id`: 新生成
- `root_task_id`: 当前 task 的 `task_id`
- `root_description`: 当前 task 的 `description`
- `status`: `open`
- `shared_context`: 从当前 task 的 `context` 提炼
- `runs`: 先放入当前这次 run

注意：

- 第一条 run 不代表“一定需要 resolver”
- 它只是先进入缓存，等 DM 决定是否还要追加同窗口动作

### 2. 追加 Run

如果 DM 判定“还有同窗口动作”，则：

1. 当前 `active_window` 保持 `open`
2. 新的 DM 指令重新进入 `planner`
3. `planner` 产出新的 `TaskExecution`
4. 新任务走 `task_approval -> executor`
5. 新的 `ExecutionResult` 被转换为 `ResolutionWindowRun`
6. 追加到 `active_window.runs`

这一步只做收集，不做写回。

## 3. 关闭 Window

关闭时机：

- `executor` 完成后
- 系统询问 DM 是否还有同窗口高优先级动作
- DM 明确回答“没有”

此时：

- `active_window.status = ready`
- 工作流进入 `resolver`
- `resolver` 输出 `ResolutionResult`
- `pending_resolution = resolution_result`
- `active_window.status = resolved`

## 4. 提交 Window

`commiter` 的输入改为优先读取 `pending_resolution`：

- 如果存在 `pending_resolution`，只写入 `final_field_changes`
- 如果不存在 `pending_resolution`，才走旧的直接写回路径

提交完成后清理：

- `active_window = None`
- `pending_resolution = None`

## 建议新增的节点

最清晰的版本是把当前流程改成：

1. `planner`
2. `task_approval`
3. `executor`
4. `window_review`
5. `resolver`
6. `commiter`

### `window_review` 的职责

`window_review` 是这次收集设计的核心节点。

它负责：

- 把本次 `TaskExecution + ExecutionResult` 写入 `active_window`
- 询问 DM 是否继续追加同窗口动作
- 决定下一步是回到 `planner`，还是直接进入 `resolver`

它不负责：

- 合并冲突
- 写回 world-state
- 自动生成新 reaction

## `window_review` 的交互建议

最小可行版本里，`window_review` 应中断并要求 DM 明确回答以下信息：

```json
{
  "type": "resolution_window_review",
  "window_id": "window_001",
  "root_description": "马利克对艾尔德拉施放魔法飞弹",
  "latest_run": {
    "task_id": "task_magic_missile_001",
    "description": "马利克对艾尔德拉施放魔法飞弹",
    "narration": "魔法飞弹将造成 11 点力场伤害。"
  },
  "options": [
    "append_same_window_action",
    "close_window"
  ]
}
```

如果 DM 选择追加，则再提供：

- `user_input`: 追加动作的自然语言描述
- `priority`: 这次 run 的结算优先级，可选

例如：

```json
{
  "action": "append_same_window_action",
  "user_input": "艾尔德拉用反应施放护盾术",
  "priority": 5
}
```

如果 DM 选择关闭：

```json
{
  "action": "close_window"
}
```

## priority 如何收集

这是收集设计里最关键的一个点。

### V1：由 DM 显式提供

最稳妥的最小方案：

- `planner` 仍然只负责任务规划
- `window_review` 在追加动作时允许 DM 显式给一个 `priority`
- 系统不自动推断规则先后

优点：

- 最容易实现
- 最不容易“自作聪明”
- 适合先验证 window 机制是否顺手

缺点：

- DM 负担略高

### V1.5：提供默认 priority

如果 DM 没有显式提供 `priority`，则使用一个确定性的默认规则：

- 新追加动作的默认 `priority`，比当前活跃窗口中最高优先级还要更高一级
- 由于本设计中数值越小代表越高优先级，所以实现上可写为：
  `default_priority = min(existing_priorities) - 1`
- 如果当前 window 里还没有任何 run，则 root run 仍使用固定起始值，例如 `10`

例如：

- root run 为 `priority = 10`
- 第一次追加动作如果未显式指定，则默认取 `9`
- 再下一次追加如果仍未显式指定，则默认取 `8`

这样可以保证：

- 新追加的动作天然满足“比当前窗口内已有动作优先级更高”
- 默认行为与“DM 正在补入更高优先级响应”的设计目标一致
- 即使 DM 不手动填写，也不会破坏 resolver 的排序前提

如果 DM 显式给了 `priority`，则以 DM 输入为准。

### 不建议的版本

不建议在第一版就让 planner 或 executor 自动判断全部 priority，因为：

- 这其实已经接近规则裁决
- 很容易把“收集问题”变成“规则引擎问题”
- 一旦判断错，会让 resolver 输入本身失真

## shared_context 如何收集

`shared_context` 不应该简单拼接所有 run 的全文上下文，否则会越来越长。

建议 V1 规则：

- 以 root task 的 `context` 作为基础
- 只提取其中与当前窗口强相关的片段
- 保存为字符串列表，供 resolver 阅读

最小实现可直接这样做：

- 把 root task 的 `context` 按行拆分
- 保留 `[KV ...]`、`[RAG ...]`、`[规则 ...]` 这类结构化行
- 去重后放入 `shared_context`

后续追加 run 时：

- 默认不重新覆盖 `shared_context`
- 仅在新 run 明显引入新的关键规则或状态键时再追加

这样能避免 window 变成“所有 prompt 的大杂烩”。

## run 如何从现有对象生成

项目里已经有：

- `TaskExecution`
- `ExecutionResult`
- `ResolutionWindowRun.from_task_and_result(...)`

因此收集逻辑可以固定为：

1. `executor` 产出 `ExecutionResult`
2. `window_review` 读取当前 `TaskExecution`
3. 根据 `order=len(active_window.runs)` 和当前 `priority` 构造 `ResolutionWindowRun`
4. append 到 `active_window.runs`

这样不用让 `executor` 知道 window 的存在，职责更干净。

## 与 triggered_chains 的关系

V1 建议：

- `triggered_chains` 继续保留在每个 run 里
- 但在 window 未关闭前，不立刻 `_enqueue_triggered_chains`
- 只有当 `resolver` 完成并且 `commiter` 写回后，再决定是否把这些 chain 入队

原因是：

- 有些 chain 依赖于最终是否命中、是否生效
- 如果主动作后来被反制，提前入队的 chain 可能变成脏数据

更稳妥的策略是：

- window 内先只缓存 triggered chain
- 由 resolver 或后处理步骤决定哪些 chain 仍有效

如果暂时不想扩大 resolver 职责，那么 V1 可以保守处理为：

- window 模式下先不自动入队 `triggered_chains`
- 只把它们保留在 run 中
- 后续再设计“resolved chain filter”

## 最小接入方案

建议按以下顺序实现：

1. 在 `AgentState` 中增加 `active_window` 与 `pending_resolution`
2. 新增 `window_review` 节点，接在 `executor` 后面
3. `window_review` 负责打开、追加、关闭 `ResolutionWindow`
4. 新增 `resolver` 节点，消费 `active_window`
5. `commiter` 改为优先消费 `pending_resolution.final_field_changes`
6. 暂时关闭 window 模式下的 `triggered_chains` 自动入队

这样改动面相对可控，而且不会要求一次性重写整个工作流。

## 不建议的实现方式

- 不建议让 `executor` 直接写 window，因为这会让单步执行器知道过多工作流细节
- 不建议让 `commiter` 同时承担 resolver 职责，因为它的边界应该保持为“只提交最终结果”
- 不建议一开始就做自动 reaction 检测，因为这会掩盖真正的 window 收集问题

## 一个完整示例

### 第一次执行

- DM 输入：`马利克对艾尔德拉施放魔法飞弹`
- `planner` 产出主任务
- `executor` 产出魔法飞弹结果
- `window_review` 创建 `active_window(window_001)`
- run0:
  `order=0`, `priority=10`

### DM 追加反应

- `window_review` 询问后，DM 选择追加：
  `艾尔德拉用反应施放护盾术`
- 新任务重新进入 `planner -> executor`
- `window_review` 把护盾术结果追加为 run1:
  `order=1`, `priority=9`（若 DM 未显式指定，则取默认值）

### DM 关闭窗口

- `window_review` 再次询问
- DM 选择 `close_window`
- `active_window.status = ready`
- 进入 `resolver`
- `resolver` 产出 `ResolutionResult`
- `commiter` 只写回 `final_field_changes`

## 非目标

这份文档暂时不定义：

- DM 交互 UI 的最终展示形式
- `priority` 的自动推断算法
- `shared_context` 的最佳压缩策略
- `triggered_chains` 的最终裁决机制

这些都可以在 window 收集链路跑通后再细化。

## 建议结论

如果要先做一个稳定、最容易落地的版本，建议采用：

- 新增 `window_review` 节点
- `active_window` 作为唯一收集容器
- `priority` 先由 DM 显式提供
- `shared_context` 先基于 root task 提炼
- `triggered_chains` 在 window 模式下先缓存、不自动入队

这样我们先解决“怎么收集”，再解决“怎么聪明地收集”。
