# 项目架构分析文档

## 目标

本文从架构视角分析当前项目的代码组织、职责边界和重复实现情况，重点回答两个问题：

- 当前代码里是否存在明显冗余
- 哪些设计可以收敛得更清晰，以便后续继续演进

这份文档基于当前代码版本的静态审阅，不包含运行时压测或线上行为验证。

## 总体结论

这个项目的主流程已经比较清楚：

- `planner` 负责把 DM 输入转成任务
- `executor` 负责执行单步任务并产出字段级变更
- `resolver` 负责合并同一结算窗口内的多个执行结果
- `commiter` 负责最终写回 world-state

也就是说，系统的主干设计是成立的，类型模型也已经初步稳定。

但当前项目已经从“可工作的原型”进入“需要收口设计”的阶段，主要问题不在于功能跑不通，而在于以下几类代码开始增多：

- 同一类上下文解析在多个模块重复实现
- 同一类 fallback 逻辑在多个位置各自维护
- workflow 节点里掺入了越来越多领域规则和写回细节
- 一些核心字段的语义还不够稳定，导致前后节点都在补救

如果继续按现在的方式叠功能，后续维护成本会明显上升。

## 当前架构概览

当前代码大致可以分为 5 层：

### 1. Agent 调用层

- `src/agents/base.py`
- `src/agents/deep_planner.py`
- `src/agents/executor.py`
- `src/agents/resolver.py`

这一层负责：

- 创建和调用 LLM
- 组织 prompt
- 执行 structured output
- 在失败时做 fallback 和 sanitize

### 2. Workflow 编排层

- `src/workflow/graph.py`
- `src/workflow/nodes.py`

这一层负责：

- 组织 `planner -> task_approval -> executor -> window_review -> resolver -> commiter`
- 维护 `AgentState`
- 驱动 LangGraph 节点跳转

### 3. 类型和契约层

- `src/types.py`

这一层负责：

- 定义任务、执行结果、窗口、合并结果等核心模型
- 对松散 JSON 输入做模型归一化

### 4. 工具与状态层

- `src/tools/toolkit.py`
- `src/tools/kv_state.py`
- `src/utils/kv_patch.py`

这一层负责：

- world-state 读写
- 字段级 patch
- evaluate / read / search / write_fields 等工具能力

### 5. Skill 与意图识别层

- `src/skills/__init__.py`
- `src/skills/intent_detector.py`
- `skills/*`

这一层负责：

- 维护 skill 注册表
- 识别意图
- 将技能内容拼接给 planner

## 当前设计的优点

在指出问题之前，先明确当前设计里值得保留的部分。

### 1. 主流程边界已经成型

`planner`、`executor`、`resolver`、`commiter` 的职责方向是清晰的。即使局部还存在越界，至少整体架构不是混乱堆叠，而是有主线可循。

### 2. 类型模型起到了“防漂移”作用

`TaskExecution`、`ExecutionResult`、`ResolutionWindow`、`ResolutionResult` 这些类型已经把核心数据流稳定下来。后续重构时，完全可以在不改大契约的情况下收敛内部实现。

### 3. `BaseAgent` 的统一调用思路是对的

`BaseAgent` 已经把模型创建、结构化输出和 fallback 逻辑集中起来，这使得 planner / executor / resolver 不需要各自再造一套调用协议。

### 4. 结算窗口设计方向是正确的

把“多步即时反应”放进 `ResolutionWindow`，再由 resolver 做统一裁决，这个方向比把所有即时响应都压进单次 executor 更健康，也更容易拓展。

## 主要问题

## 1. `workflow/nodes.py` 职责过重

当前 `src/workflow/nodes.py` 不只是 workflow 节点文件，它实际上同时承担了：

- 节点编排
- 调试输出
- 中断交互协议
- 结算窗口维护
- 默认优先级策略
- fallback resolver
- commit 写回过滤
- triggered chain 入队

这会带来几个问题：

- 节点文件越来越像“总控脚本”
- 流程控制和领域规则强耦合
- 后续要改 window 规则、commit 规则或交互协议时，很容易影响整条链路

比较典型的信号是：

- `_extract_window_shared_context()`
- `_default_priority()`
- `_materialize_resolution()`
- `create_commiter_node()`

这些逻辑本质上都不是“节点跳转”本身。

### 建议

把这部分拆成至少 3 个职责清晰的模块：

- `workflow/nodes.py`
  只保留 `state -> Command`
- `workflow/window_service.py`
  负责窗口构建、追加 run、优先级、共享上下文合并
- `workflow/commit_service.py`
  负责字段变更过滤、payload 生成、写回结果收集

## 2. resolver fallback 逻辑重复维护

当前“最小 resolver”算法有两份实现：

- `src/workflow/nodes.py` 中的 `_materialize_resolution()`
- `src/agents/resolver.py` 中的 `_build_fallback_result()`

两者做的事情本质相同：

- 按 `priority` / `order` 排序
- 同一路径变更后者覆盖前者
- 旧变更进入 `discarded_field_changes`

这类重复最大的问题不是代码多，而是后续容易分叉：

- 一个地方修了，另一个地方忘了修
- 测试覆盖的实现不是运行时真正调用的实现
- 文档描述和实际 fallback 行为逐渐不一致

### 建议

保留一份纯函数实现，例如：

```python
def materialize_resolution(window: ResolutionWindow) -> ResolutionResult:
    ...
```

然后让：

- `workflow` 测试
- `ResolverAgent` 的 fallback
- 文档中的“最小 resolver”说明

全部复用这一份实现。

## 3. commit 写回逻辑和工具能力重叠

当前 `create_commiter_node()` 中有两段几乎相同的代码：

- 处理 `resolution.final_field_changes`
- 处理 `result.field_changes`

两段代码都在做：

- path 拆解
- 根 key 存在性判断
- payload 构造
- 已提交变更收集

而 `WriteFieldsTool` 自己又做了一遍字段级写回处理。

这说明当前设计里有两层在做相似工作：

- workflow 在准备“可写字段变更”
- tool 在真正应用字段变更

但两者之间的边界没有彻底拉开。

### 建议

明确两层职责：

#### 方案 A

workflow 只做业务决策，完全不做字段写回预处理，直接把原始 `StateChange` 交给一个专用的 commit service。

#### 方案 B

workflow 负责过滤，tool 只负责执行，不再内含额外的路径语义判断。

在当前项目里，更推荐方案 A，也就是新增一个显式的 `ChangeCommitService`，由它来完成：

- 校验 path 合法性
- 生成 `write_fields` payload
- 统计成功应用的变更
- 返回结构化 commit 结果

这样 `create_commiter_node()` 就可以退化成一个非常薄的调度节点。

## 4. KV 上下文解析散落在多个模块

这类重复是目前项目里最明显、也最值得尽快收敛的一类。

现在与 `[KV ...]` 相关的解析逻辑分散在多个地方：

- `DeepPlannerAgent._extract_context_keys()`
- `ExecutorAgent._extract_context_keys()`
- `ExecutorAgent._extract_old_field_value_from_context()`
- `types._build_task_state_snapshot()`
- `types._match_context_kv_line()`

这些逻辑本质上都属于同一个问题域：

- 如何从 task context 中提取结构化 world-state 信息

如果继续扩展：

- planner 想知道有哪些 root key
- executor 想知道旧字段值
- resolver 想知道共享上下文里的路径
- commiter 想知道哪些 key 当前存在

就会继续有更多相似 helper 冒出来。

### 建议

新增一个统一的解析模块，例如：

- `src/domain/context_parser.py`

集中提供如下能力：

- `extract_kv_keys(text) -> list[str]`
- `extract_kv_snapshot(text) -> dict[str, str]`
- `extract_field_value(text, path) -> str | None`
- `extract_kv_fields(text, root_key) -> list[str]`
- `split_field_path(path) -> tuple[str, str] | None`

这样 planner / executor / types / workflow 都只依赖一套解析规则。

## 5. `write_targets` 的语义不稳定

当前 `TaskExecution.write_targets` 是 `list[str]`，但它实际承载了两种不同语义：

- root key，例如 `Aldera.combat`
- 字段路径，例如 `Aldera.combat.HP`

这直接导致：

- planner 里需要 `_normalize_write_targets()` 去猜用户或模型到底输出了哪一种
- executor 里又要对结果做二次过滤
- commit 阶段还要继续做路径合法性判断

这种设计短期灵活，但长期代价很高，因为每一层都要做语义纠偏。

### 建议

优先考虑以下两种收敛方式之一：

#### 方案 A

`write_targets` 只允许字段级 path。

优点：

- 语义最清晰
- executor 和 commiter 的过滤逻辑会明显变薄

缺点：

- planner prompt 需要更严格
- planner 后处理要更强

#### 方案 B

引入显式结构类型，例如：

```python
class WriteTarget(BaseModel):
    root_key: str
    field: str | None = None
```

优点：

- 能保留“先写 root，再推断 field”的弹性
- 语义比裸字符串清晰

缺点：

- 会牵涉 schema 改动

从长期维护角度看，更推荐方案 A，即最终只保留字段级 path。

## 6. planner 内部承担了较多前处理责任，但不必重构 `DeepPlannerAgent` 本体

`DeepPlannerAgent` 当前不只是在“规划任务”，它还承担了：

- 意图识别
- skill 选择
- actor / target 归一
- write target 推断
- 字段级 path 补全

这些能力虽然都和 planner 有关，但抽象层次并不一致。

更准确地说，这里面至少混了三类职责：

- 输入理解
- 规则化归一
- 任务规划

### 建议

这里更推荐的方向不是重构或替换 `DeepPlannerAgent`，而是保留它作为 planner 的唯一入口，同时把它依赖的重复逻辑逐步外提。

更稳妥的方式是：

- 保留 `DeepPlannerAgent` 对外职责不变
- 不调整 planner 在主流程中的位置
- 只把可复用的解析和归一逻辑提取成 helper 或 service

例如可以逐步外提：

- skill 选择入口
- actor / target 归一逻辑
- `write_targets` 归一逻辑
- context / KV 解析逻辑

这样做的好处是：

- planner 角色保持稳定
- 风险小，不会影响主流程认知
- 以后要调整技能策略或任务归一策略时，不需要重写 `DeepPlannerAgent`

## 7. skill 入口存在双轨实现

当前项目里同时存在：

- LLM-based `IntentDetector`
- 关键词版 `detect_intent_with_keywords()`

但 `DeepPlannerAgent.plan()` 现在实际走的是关键词版。

这会造成一个不太健康的状态：

- 代码里存在两套入口
- 文义上都像“主入口”
- 但运行时真实路径并不直观

### 建议

只保留一个公开入口，例如：

```python
select_skill(user_input: str) -> tuple[str, Skill | None]
```

内部再决定：

- 先走 LLM
- 失败后走关键词

或：

- 根据配置选择模式

重点不是选哪种方式，而是把调用入口收敛成一条。

## 8. `types.py` 已经开始承担领域工具职责

`src/types.py` 当前除了定义模型，还包含了不少辅助逻辑：

- `_stringify_change_values()`
- `_build_task_state_snapshot()`
- `_match_kv_appendix()`
- `_match_context_kv_line()`

这些逻辑不是“类型定义”本身，而是数据解释与转换。

短期放在一起很方便，但长期会出现两个问题：

- `types.py` 逐渐变成大杂烩
- 一些函数会被更多业务模块依赖，反而让类型层变重

### 建议

按职责拆开：

- `types.py`
  只保留类型和模型 validator
- `context_parser.py`
  处理 context / snapshot / kv line 解析
- `normalizers.py`
  处理“松散 JSON 转标准结构”的辅助逻辑

如果不想一次拆太大，最少也应先把 `_build_task_state_snapshot()` 和 KV 正则解析迁出去。

## 可识别的冗余代码清单

下面列出当前最值得优先收敛的重复点。

### 高优先级

- resolver fallback 双实现
- commiter 中两段几乎相同的 payload 构造逻辑
- planner / executor 重复实现 `_extract_context_keys()`
- KV 旧值提取和 snapshot 解析分散在 `executor.py` 与 `types.py`

### 中优先级

- skill 选择的双轨入口
- workflow 中大量重复的打印和调试格式化逻辑
- `WriteFieldsTool` 与 commit 节点都在做路径和字段语义处理

### 低优先级

- `DeepPlannerAgent` 和 `ExecutorAgent` 中一些“本轮允许 key/path”的字符串拼装 helper
- 类型模型里的松散输入归一模式高度相似，可以进一步抽象

## 更清晰的目标架构

在不推翻现有设计的前提下，一个更清晰的结构可以是下面这样：

### 1. Agent 层只关心 LLM 行为

- `DeepPlannerAgent`
- `ExecutorAgent`
- `ResolverAgent`

职责：

- prompt 组装
- agent 调用
- structured output
- sanitize / fallback

不负责：

- 复杂上下文解析
- commit 逻辑
- skill 选择策略本身

### 2. Domain Service 层负责规则性逻辑

建议新增：

- `context_parser.py`
- `resolution_service.py`
- `change_commit_service.py`
- `skill_selector.py`

如果后续确实需要，再考虑补充：

- `task_normalizer.py`

职责：

- 处理领域约束
- 统一“最小规则引擎”
- 消除各层重复 helper

### 3. Workflow 层只负责编排

workflow 节点理想上应该只做：

- 读 state
- 调 service / agent
- 写 state
- 返回 `Command`

不要在节点内部再堆太多业务细节。

### 4. Tool 层只负责基础能力

tool 应该像底层能力适配器：

- 读状态
- 写状态
- 查规则
- 做计算

而不是承担上层的业务决策。

## 推荐重构顺序

这里推荐一个低风险、渐进式的顺序。

## 第一阶段：收敛重复实现

目标：

- 不改核心契约
- 只消除明显冗余

建议动作：

- 抽出统一的 `materialize_resolution()`
- 抽出统一的 `context_parser`
- 抽出 `split_field_path()` / `extract_kv_keys()` 等公共 helper
- 合并 commiter 中重复的 payload 构造逻辑

这是收益最高、风险最低的一步。

## 第二阶段：收窄 workflow 职责

目标：

- 让 `nodes.py` 只剩流程编排

建议动作：

- 拆出 `window_service`
- 拆出 `commit_service`
- 把打印和调试输出整理成统一 helper

做完这一层后，workflow 的可读性会提升非常明显。

## 第三阶段：收敛 planner 周边输入链路

目标：

- 在不改 `DeepPlannerAgent` 角色的前提下降低其内部负担

建议动作：

- 引入统一 `SkillSelector`
- 收紧 `write_targets` 的语义
- 把 context / KV 解析 helper 外提复用

如果后面这部分规则继续变复杂，再考虑是否需要单独的 `TaskNormalizer`。

这一步会影响 prompt 和后处理，但会让后续新能力接入更稳。

## 第四阶段：考虑更强的领域抽象

如果项目后续继续做复杂结算，再考虑进一步引入：

- 显式的 `WorldStatePath`
- 显式的 `WriteTarget`
- 更结构化的 run effect / discarded reason 模型

这一阶段不是当前必须做的，但属于中长期自然方向。

## 最终建议

从当前代码状态看，这个项目没有出现“必须推倒重来”的问题。

更准确的判断是：

- 主体架构方向正确
- 类型契约已经具备演进基础
- 但重复实现和职责混杂开始增多

最值得优先处理的不是“大改框架”，而是三件事：

1. 收敛重复的 KV/context 解析
2. 收敛重复的 resolver fallback 和 commit 写回逻辑
3. 把 workflow 中的领域规则逐步下沉到 service 层

如果这三步做完，项目的清晰度会提升一个台阶，而且不会伤到现有主流程。

## 附：一句话判断

当前项目已经具备一个不错的雏形，问题不在于架构方向错了，而在于很多“原型期方便的实现”正在变成“长期维护期的重复负担”。现在正是适合做第一轮收敛的时间点。
