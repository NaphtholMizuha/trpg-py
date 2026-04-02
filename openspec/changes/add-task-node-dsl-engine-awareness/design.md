## 上下文

当前 planner workflow 已经是明确的两阶段结构：`task_node` 先产出 TaskDraft，`dsl_node` 再将其翻译为 TaskDocument，最后由 engine 在运行期执行并解析掷骰、伤害、豁免结果等动态值。但 `task_node` 的提示词还不够明确地表达这种下游阶段边界，导致第一阶段偶尔把“未来执行时才会得到的随机结果”误判为前置缺失信息。

这种误判最典型的表现是：
- 把伤害骰结果、攻击掷骰结果、豁免成败等运行期值写进 `missing_info`
- 让 TaskDraft 看起来像是在等待人类补充一个实际上应由 engine 计算的值

## 目标 / 非目标

**目标：**
- 让 `task_node` prompt 明确知道后面还有 `dsl node` 和 `engine`。
- 明确 `task_node` 的职责是输出执行意图、所需状态路径和决策结构，而不是提前求出随机运行结果。
- 收紧 `missing_info` 语义：只有真正缺失的状态、规则身份、路径绑定或前置决策才进入 `missing_info`。
- 明确运行期随机性数值不属于 `missing_info`。

**非目标：**
- 不修改 `dsl_node` 的核心执行逻辑。
- 不修改 engine 的掷骰或运行期求值机制。
- 不要求 `task_node` 预先计算攻击结果、伤害结果或豁免结果。

## 决策

### 决策 1：通过 prompt 显式声明下游阶段职责
- 选择原因：问题根源是第一阶段对 workflow 边界理解不足，而不是代码执行链路缺失。
- 替代方案：在 TaskDraft schema 中新增字段区分“运行期值”和“缺失值”。
- 未选择原因：会扩大 schema 变更面，而当前问题可以先通过 prompt 约束解决。

### 决策 2：把 `missing_info` 定义为“阻止 drafting 的真实前置缺口”
- 只允许以下类型进入 `missing_info`：
  - 无法确认的 exact path
  - 未确认的规则身份
  - 缺失的状态值或配置值
  - 缺少会改变执行形状的人类决策
- 禁止把以下类型写进 `missing_info`：
  - 未来掷骰结果
  - 未来伤害总值
  - 未来命中 / 未命中结果
  - 未来豁免成功 / 失败结果

### 决策 3：用 few-shot 直接展示“随机结果不是 missing_info”
- 选择原因：这类边界用抽象规则讲一次不一定稳，few-shot 更容易让模型内化。
- 替代方案：只在 requirements 中补一句禁止规则。
- 未选择原因：没有示例时，模型容易回到“既然现在不知道，就先放 missing_info”的默认模式。

## 风险 / 权衡

- [风险] prompt 过度强调“不要写 missing_info”后，模型可能把真正缺失的信息也忽略掉
  - 缓解措施：同时明确 `missing_info` 的正例和反例，强调只有运行期随机结果不应进入该字段。

- [风险] 模型可能把某些非随机但尚未确认的数值也误归为 engine 负责
  - 缓解措施：在 prompt 中明确区分“未来由 engine 计算的结果”与“当前必须先确认的 state path / resource path / rule identity”。

- [权衡] 只改 prompt 不能从类型系统层面强制这一边界
  - 取舍原因：当前先用最小改动改善 task drafting 行为；如果未来仍不稳，再考虑 schema 级约束。
