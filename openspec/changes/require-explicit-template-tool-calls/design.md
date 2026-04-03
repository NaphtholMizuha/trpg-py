## 上下文

上一轮变更已经把 `template` 作为一个工具对象接进 `dsl_node`，但当前实现并没有让 agent 真正调用它，而是在 `DslNode.run()` 里由宿主代码先推断查询参数、先执行模板查询、再把 `template_lookup` 作为 prompt 上下文注入模型。结果表面上“有 template 工具”，实际上却绕开了工具调用语义。

这带来几个直接问题：
- 用户、日志和 smoke 只能看到 `lint` 调用，看不到 `template` 是否真的被用过。
- `template` 查询不计入 agent 的工具预算，导致“工具边界”与“实际推理成本”不一致。
- 宿主预取会掩盖模型分类错误，难以区分“模型没有调用 template”和“模板没命中”。
- prompt 被迫维护 `template_query_hint` / `template_lookup` 这类宿主注入字段，边界很别扭。

当前需要的不是“继续预取得更聪明”，而是把 `template` 收回到与 `lint` 一样的真实 ReAct/tool-use 边界。

## 目标 / 非目标

**目标：**
- 让 `template` 成为 `dsl_node` agent 显式调用的真实工具，而不是宿主预取的伪工具。
- 让 `template` 调用与 `lint` 一样可观察、可计入工具预算、可在测试中断言。
- 收紧 `dsl_node` prompt，使其明确先分类、再调用 `template`、再生成候选 DSL、再调用 `lint`。
- 去掉宿主注入的 `template_query_hint` / `template_lookup` prompt 负担，恢复清晰的工具边界。

**非目标：**
- 不否定 `template` 工具本身或其模板资产。
- 不在本次把 `dsl_node` 改成纯确定性编译器。
- 不要求 `template` 覆盖更多任务族；本次聚焦调用方式而不是模板扩容。
- 不改变 `lint` 作为最终合法性守门的角色。

## 决策

### 决策 1：禁止宿主侧预取 template

- 选择原因：宿主预取让“工具存在”与“agent是否使用工具”脱钩，破坏可观察性与边界一致性。
- 方案：移除 `DslNode.run()` 内的模板预取逻辑，不再在 agent 调用前执行 `template.invoke(...)`。
- 替代方案：保留预取，同时允许 agent 事后再次调用 `template`。
- 未选择原因：会形成双路径真相，用户仍无法确信当前候选到底来自哪次模板查询。

### 决策 2：template 必须像 lint 一样参与 agent 的真实工具回路

- 选择原因：用户真正想要的是“模型先查模板再写 DSL”，而不是“宿主替模型查好再暗塞进去”。
- 方案：`dsl_node` 只把 `template` 和 `lint` 作为工具挂给 agent；模板查询必须由 agent 在推理过程中显式触发。
- 替代方案：把 `template` 结果继续作为 prompt 附件，但在日志里额外打印预取痕迹。
- 未选择原因：日志修饰不能替代真实工具调用语义。

### 决策 3：prompt 改成指导显式 tool-use，而不是消费宿主注入对象

- 选择原因：一旦没有预取，prompt 就必须明确告诉模型：先用少量受控枚举字段查模板，再基于模板填充 DSL。
- 方案：移除 `template_query_hint` / `template_lookup` 输入块，保留任务分类和受控枚举说明，要求 agent 主动调用 `template`。
- 替代方案：保留宿主注入 hint，只移除 lookup。
- 未选择原因：hint 仍会鼓励“宿主替我做了一半”，边界依然不干净。

### 决策 4：为 template 工具增加调用日志或等价诊断信息

- 选择原因：如果没有类似 `lint` 的输入/输出痕迹，用户依然无法在 smoke 中确认 agent 是否真的调用了 `template`。
- 方案：为 `template` 增加输入/输出日志，至少记录查询字段、命中状态、模板 ID 和是否使用回退。
- 替代方案：只在测试替身里断言调用。
- 未选择原因：测试可断言不代表真实运行可观测。

## 风险 / 权衡

- [风险] 去掉预取后，模型可能因为忘记先调 `template` 而回退到 few-shot 记忆
  - 缓解措施：prompt 明确把“先 `template` 后 `lint`”写成默认流程，并用测试断言 prompt 里不再依赖宿主注入字段。

- [风险] 真实工具回路会增加一次模型-工具往返
  - 缓解措施：`template` 是只读、低成本工具；增加一次调用比继续接受边界失真更值得。

- [风险] 如果 `template` 未命中，agent 仍可能自由发挥
  - 缓解措施：要求 agent 使用 `unknown` 做保守查询，并让 `lint` 继续兜底；同时记录未命中状态，便于后续扩模板。

- [风险] 日志增加后 smoke 输出更吵
  - 缓解措施：只记录关键信息：查询字段、状态、模板 ID、fallback_used。

## Migration Plan

1. 在 `dsl_node` 中删除宿主预取与对应 prompt 注入。
2. 更新 `template` 工具日志与说明，使其行为和 `lint` 一样可观察。
3. 调整 `dsl_node` prompts，改为要求 agent 显式调用 `template`。
4. 补充 workflow / smoke / unit tests，验证运行时发生真实 `template` 工具调用。
5. 用 smoke 重新观察日志，确认 `template` 与 `lint` 都可见。

## Open Questions

- `dsl_node` 是否还需要宿主提供极薄的“分类提醒”，还是应该完全把分类也交给 agent 自己完成？
- `template` 未命中时，prompt 是否应要求“先再查一次更保守模板，再考虑 freehand”，还是直接允许进入 freehand + lint？
