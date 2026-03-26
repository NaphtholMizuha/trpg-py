## 上下文

当前 planner 同时处在两套路径语义之间工作：
- 在最终 `TaskDocument` 中，执行器通过 `$ref` 解析 `state.*`、`context.*` 和 `result.*` 命名空间引用。
- 在 `fetch_keys` 与 `reads` 工具调用中，工具直接面向 store 的真实点路径工作，例如 `actors.aldera.ac`。

这两套语义本身并不冲突，但当前 prompt 只反复强调了 `TaskDocument` 的 `state.*` 引用示例，却没有明确告诉模型“工具参数不能携带 `state.` 前缀”。结果是 planner 在默认 smoke 中把 `state.actors...` 直接送进 `fetch_keys` / `reads`，从而误判 state 证据不存在。

这次变更主要触及 `config/prompts/` 和 prompt 相关测试。问题虽然表现在真实 smoke 运行中，但当前最小、最可控的修复面是 prompt 语义澄清，而不是改动 store、工具 API 或执行器引用解析逻辑。

## 目标 / 非目标

**目标：**
- 让 planner prompt 显式区分“工具路径”与“`TaskDocument` `$ref` 路径”两种语法。
- 让 prompt 中关于 `fetch_keys` 与 `reads` 的说明直接给出裸 store 路径示例，例如 `actors.goblin_1.ac`。
- 让 canonical example 或相邻说明展示从工具路径到最终 `$ref` 路径的转换关系。
- 为默认 prompt 行为补充测试，防止后续再把路径命名空间混用。

**非目标：**
- 不修改 `fetch_keys` 或 `reads` 的运行时语义，不让它们额外兼容 `state.` 前缀。
- 不修改执行器对 `$ref` 的 `state/context/result` 命名空间解释逻辑。
- 不扩大为“重写 planner 全套 prompt 策略”或“重新设计 smoke world state 结构”的变更。

## 决策

### 决策 1：优先修 prompt 语义，而不是改工具兼容层

当前 `fetch_keys` / `reads` 与 store 测试语义是一致的，真实状态根路径也稳定是 `actors...`。问题出在模型被 prompt 误导，把 `$ref` 语法复制到了工具参数里。因此最小修复应该先落在 prompt 上，让模型学会区分“查证时用裸路径”“出文档时用命名空间引用”。

考虑过的替代方案：
- 让工具自动接受 `state.` 前缀：可以降低一类错误，但会把工具真实语义和执行器引用语义混成更模糊的一团。
- 改 smoke world state，使其根节点变成 `state`：会与现有 store API、测试和执行器语义产生更大范围的错位。

### 决策 2：在 user prompt 中显式并列展示两套路径格式

仅靠一句“use fetch_keys to discover candidate state paths”过于抽象。设计上应在 prompt 里直接并列写出：
- 工具路径示例：`actors.aldera.ac`
- `$ref` 路径示例：`state.actors.aldera.ac`

同时明确说明：工具返回的是裸 store 路径；planner 在写入 `TaskDocument` 时，需要把对应 state 引用写成 `state.<tool_path>` 风格。

考虑过的替代方案：
- 只改 canonical example，不新增文字规则：仍然容易让模型把示例中的 `state.*` 误投射到工具参数。
- 只在 system prompt 提醒，不改 user prompt：模型更容易被 user prompt 中的长示例覆盖。

### 决策 3：测试聚焦“提示词是否传达了边界”，而不是伪造复杂 agent 行为

这次变更的目标是防止默认 prompt 再次误导模型，因此测试重点应放在 prompt 文案本身，例如断言默认 user prompt 同时包含裸路径示例与命名空间引用说明。必要时可以补一个更贴近 smoke 失败案例的断言，确保提示词明确禁止把 `state.` 前缀直接传给 `fetch_keys` / `reads`。

考虑过的替代方案：
- 只依赖真实 smoke 结果回归：反馈慢，而且容易被模型随机性影响。
- 在单测里模拟完整 agent 推理过程：成本高，且难以稳定证明 prompt 边界是否表达清楚。

## 风险 / 权衡

- [prompt 增加额外说明后变长] → 保持改动聚焦在路径语义，不顺带加入其他新策略，避免噪声继续上升。
- [仅靠 prompt 仍不能百分百消除模型误用] → 通过更直接的示例和测试守护先降低主要误导源，再视真实效果决定是否需要后续工具兼容。
- [canonical example 与文字规则不一致] → 设计上要求同步更新示例与工具说明，避免“规则说一套、例子演一套”。

## 迁移计划

1. 更新 `planner_system.txt` 与 `planner_user.txt`，加入工具路径 vs `$ref` 路径的显式区分。
2. 调整 canonical example 或补充就近示例，展示 `actors...` 到 `state.actors...` 的映射关系。
3. 更新 prompt 相关测试与必要的 smoke 断言，确保该边界被固定下来。
4. 用默认 smoke 场景复核 planner 不再因为 `state.` 前缀误用而过早进入 `needs_human`。

## 开放问题

- 是否需要在 prompt 中明确写出“不要把 `state.` 前缀传给 fetch_keys/reads”这样的禁止性语句，还是示例和对照说明已经足够。
- 如果后续仍偶发误用，下一步应优先补更强的 prompt 约束，还是再评估工具层做容错兼容。
