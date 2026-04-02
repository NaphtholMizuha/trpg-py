## 上下文

这次 smoke 已经把问题暴露得很清楚：`dsl_node` 不是完全无法理解 `TaskDraft`，而是在缺少目标语言约束时，会自然回退到模型自己熟悉的“通用工作流 DSL”。例如它会生成：
- `read`
- `calculate`
- `invoke`
- `conditional`
- `write`

但当前 engine 实际只支持 [`select/check/damage/heal/resource/effect/state`] 这一小组 step type，以及每个 type 下更窄的 kind 集合。这个真相现在主要存在于运行期校验逻辑里，而不在 `dsl_node` 的结构化输出 schema 或 prompt 里，因此问题总是被拖到 lint 之后才暴露。

另一个并行问题是 `lint` 的反馈粒度。当前它可以很好地区分“结构非法”“语义非法”“工具错误”，但在语义阶段通常是遇到第一个 `ValidationError` 就返回。对于人类排查来说，这意味着一次只看到一个洞；对于未来的 `dsl_node -> lint -> repair` 回路来说，这意味着修复效率会很低。

这次变更的目标是做一个短期、工程化的收紧方案，而不是立刻把 `TaskDraft` 重构成新的 IR，也不是扩展 engine 原语集合。

## 目标 / 非目标

**目标：**
- 让 `dsl_node` 明确知道当前 engine 真实支持的 DSL 词表，而不是自由生成通用步骤名称。
- 让 `TaskDocument` 的结构化输出 schema 更接近 engine DSL，而不是只验证“像 JSON 对象”。
- 让 `dsl_node` prompt 学会把 `TaskDraft` 下降到现有 engine primitive。
- 让 `lint` 尽量在单轮中返回同一候选文档的多个独立错误，便于人工调试和后续自动修复。

**非目标：**
- 不在本次变更里发明新的 engine step type / kind。
- 不把 `TaskDraft` 立刻升级为全新的强类型 IR。
- 不保证 `lint` 能穷尽所有级联错误；目标是尽量汇总同一轮可安全发现的问题。
- 不要求本次直接上线完整的多轮 repair agent，只为其铺路。

## 决策

### 决策 1：先收紧 `TaskDocumentSchema` 的 DSL 边界，而不是只靠 prompt 约束

- 选择原因：如果结构化输出层仍允许任意字符串 `type/kind`，模型即使读过 prompt，也仍然可能生成项目外 DSL，然后把错误推迟到 lint。
- 方案：把 `TaskStepSchema` 至少收紧到 engine 当前支持的 `type` 枚举，并为 `kind` 增加与 `type` 对齐的受限集合；必要时可先采用“按 type 校验 kind”的渐进式方案，而不是一步做到完全判别联合。
- 替代方案：只改 prompt，不动 schema。
- 未选择原因：这样无法把错误前移到 structured output 阶段，约束力度太弱。

### 决策 2：把 `dsl_node` prompt 改写成“目标语言说明书 + translation rules + few-shot”

- 选择原因：现在 prompt 更像一句目标宣言，而不是编译目标定义。模型知道要“生成 TaskDocument”，但不知道什么才是这个项目里的合法 TaskDocument。
- 方案：
  - system prompt 明确列出支持的 step type / kind
  - 明确列出常见最小参数要求和 ref namespace 规则
  - 明确禁止发明 `read/calculate/write/invoke` 这类项目外术语
  - user prompt 附带 translation rules，把 `reads/judgments/writes/missing_info` 和 engine primitive 的映射讲清楚
  - few-shot 专注展示 `TaskDraft -> engine primitive` 的下降过程
- 替代方案：只在 user prompt 里补几条 requirements。
- 未选择原因：模型在 system prompt 中需要看到清晰、稳定、可复用的 DSL 真相，不适合只埋在 requirements 角落。

### 决策 3：few-shot 只教“如何下降到现有 primitive”，不教新的业务 DSL

- 选择原因：如果 few-shot 继续用高层业务步骤命名，会进一步强化模型发明 `DetermineSpellUse` 之类中间 DSL 的倾向。
- 方案：few-shot 优先覆盖单体攻击、单体法术、范围法术、状态更新等最常见任务类型，并且每个示例都只使用当前 engine 支持的原语。
- 替代方案：直接用 Fireball 这一条样例做大而全 few-shot。
- 未选择原因：单个复杂样例容易让模型记住表面模式，不利于学习原语级映射。

### 决策 4：`lint` 采用“结构先聚合、语义再聚合”的错误收集策略

- 选择原因：Pydantic 结构校验本来就支持多错误返回，但语义校验现在是一个 `raise` 就退出。若不调整，`dsl_node` 后续的修复回路只能一次解决一个问题。
- 方案：
  - 保留结构校验的多错误收集
  - 新增语义问题收集器，在遍历 steps 时尽量记录每个 step 的独立错误，而不是第一次失败即终止
  - 对无法继续分析的依赖型错误保持保守，只报告当前可独立确认的问题
- 替代方案：维持当前 fail-fast 语义。
- 未选择原因：对生成式调用方反馈太差，不利于 smoke 调试和自动修正。

### 决策 5：先为 repair loop 铺路，但不把完整多轮自修复纳入本次范围

- 选择原因：真正的 repair loop 依赖更好的 prompt、schema 和 lint 结果质量。如果现在直接上 loop，只会让模型围绕模糊错误反复试错。
- 方案：本次先确保 lint 输出足够结构化、足够全面，并让 `dsl_node` 的 prompt 明确“必须满足 lint/engine DSL”。
- 替代方案：本次就实现完整的生成-校验-重写多轮循环。
- 未选择原因：会把问题面扩得太大，不利于先验证基础收紧策略是否有效。

## 风险 / 权衡

- [风险] schema 收紧后，`dsl_node` 可能从“生成错误 DSL”变成“更频繁地产生结构化输出失败”。
  - 缓解措施：这是有价值的前移失败；通过 few-shot 和 prompt 词表补齐来恢复成功率。

- [风险] 语义 lint 聚合可能把某些级联错误也一起报出来，导致噪声上升。
  - 缓解措施：只聚合“同一轮可独立确认”的错误；对后续依赖未满足导致的不确定错误保持保守。

- [风险] prompt 变长后，模型可能更守规则但更模板化。
  - 缓解措施：few-shot 保持小而强，重点教 primitive 映射，不堆砌大段说明。

## Migration Plan

1. 收紧 `TaskDocumentSchema`，让结构化输出更接近 engine 词表。
2. 更新 `planner_dsl_node` 的 system / user prompt，加入 DSL 词表、translation rules 和 few-shot。
3. 改造 lint 语义校验逻辑，使其尽量聚合多个可独立发现的错误。
4. 增加测试和 smoke 验证，确认：
   - `dsl_node` 不再轻易生成项目外 DSL
   - lint 能返回多个问题
   - smoke 输出的错误信息更适合调试

## Open Questions

- `TaskStepSchema` 是否要一步做到判别联合，还是先做“受限 type + kind 映射”这一版？
- `lint` 聚合语义错误时，是否需要为“后续步骤基于前一步非法输出”的情况增加 `blocked_by` 一类提示？
- 对 `dsl_node` 而言，第一版 few-shot 是否需要直接包含一条 Fireball 类 AoE 案例，还是先用更小的 area 示例建立原语映射？
