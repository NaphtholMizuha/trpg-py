## 上下文

现在 `task_node` 已经通过 `TaskDraft` 把任务结构、证据和缺口表达得越来越稳定，但 `dsl_node` 仍然只有极薄的一层 prompt，缺少明确的翻译边界。当前风险在于：
- `dsl_node` 可能重新理解 `TaskDraft`，而不是把它当作真相
- `missing_info` 只是字符串列表时，下游很难知道“缺口默认如何处理”
- `dsl_node` few-shot 如果自成体系，会和 `task_node` 的任务类型原型逐渐漂移

你给出的方向很清楚：`dsl_node` 只需要翻译，不需要补完；因此 `missing_info` 必须在 `TaskDraft` 层就具备默认值或默认处理语义，使下游能够直接消费。

## 目标 / 非目标

**目标：**
- 让 `missing_info` 从“自由文本缺口”演进为带默认值语义的结构化信息。
- 明确 `dsl_node` 的职责是将 `TaskDraft` 翻译为 `TaskDocument`，而不是重新做任务理解。
- 让 `dsl_node` prompt 直接消费 `task_node` 已定义的任务类型原型。
- 让 `dsl_node` few-shot 与 `task_node` few-shot 在场景类型上保持同构，降低跨阶段漂移。

**非目标：**
- 不要求 `dsl_node` 自行补充新的规则或状态检索。
- 不要求 `dsl_node` 重新判断 `missing_info` 是否合理。
- 不在本次引入新的 planner 阶段。
- 不要求 engine 立刻支持新的复杂执行语义，除非翻译契约需要显式表达默认值。

## 决策

### 决策 1：把 `missing_info` 设计成结构化条目，而不是仅保留字符串列表
- 选择原因：如果 `missing_info` 只有自然语言描述，`dsl_node` 无法“只翻译”，因为它必须再猜这个缺口的默认处理方式。
- 方案：为 `TaskDraft` 引入结构化 `missing_info` 条目，至少包含：
  - 缺口描述
  - 默认值或默认处理
  - 缺口为什么存在
- 替代方案：继续使用字符串列表，并在 `dsl_node` prompt 中要求模型自行猜默认值。
- 未选择原因：这会迫使 `dsl_node` 重新理解任务，违背“只翻译”的目标。

### 决策 2：`dsl_node` 只翻译，不补完
- 选择原因：当前两阶段工作流的核心价值，是让 `TaskDraft` 成为中间真相。如果 `dsl_node` 再次补完，会让边界重新模糊。
- 方案：prompt 明确要求 `dsl_node`：
  - 不重写任务结构
  - 不自行增加新的缺口解释
  - 不推翻 `task_node` 已确认的 judgments / evidence / states
  - 只把这些输入翻译成 `TaskDocument`
- 替代方案：允许 `dsl_node` 在翻译时顺手纠正或补全任务理解。
- 未选择原因：会导致两个阶段职责重叠，难以测试和调试。

### 决策 3：`dsl_node` few-shot 与 `task_node` 任务类型原型保持同构
- 选择原因：如果上游按“单体攻击 / 单体法术 / 范围法术 / 治疗增益 / 状态效果 / 纯查询”来组织任务稿，而下游 few-shot 又换了一套分类方式，翻译层就会漂移。
- 方案：`dsl_node` few-shot 直接沿用相同的任务类型原型，只展示“从对应类型的 TaskDraft 到 TaskDocument 的翻译”。
- 替代方案：为 `dsl_node` 单独设计另一套 few-shot 分类。
- 未选择原因：会让两个阶段对同一任务的结构切分越来越不一致。

## 风险 / 权衡

- [风险] `missing_info` 结构化后，TaskDraft schema 会发生显式变化
  - 缓解措施：在设计中把字段收敛到最小集合，只表达翻译所需信息。

- [风险] 过度强调“只翻译”后，`dsl_node` 可能在 TaskDraft 质量不足时也硬翻
  - 缓解措施：明确 `dsl_node` 仍可忠实保留 `missing_info` 的默认值语义，但不得擅自补全。

- [风险] `task_node` 与 `dsl_node` few-shot 完全同构，会带来维护成本
  - 缓解措施：保持“同构于任务类型”，而不是逐字复用；每个节点只保留本阶段所需的示例深度。

## Migration Plan

1. 为 `TaskDraft` 设计结构化的 `missing_info` 条目与默认值语义。
2. 更新 `dsl_node` prompt，明确其为纯翻译阶段。
3. 按 `task_node` 的任务类型原型重建 `dsl_node` few-shot。
4. 增加测试，验证 `dsl_node` 不会重新补完任务，且 few-shot 与 `task_node` 类型原型对齐。

## Open Questions

- `missing_info` 的默认值字段应该是自由值、有限枚举，还是二者兼容？
- `TaskDocument` 里如何承接这些默认值语义最合适：context、policy，还是专门的参数区？
- 当 `TaskDraft` 已经明显不完整时，`dsl_node` 是继续翻译并保留默认值，还是返回更显式的“不完整但可翻译”结构？
