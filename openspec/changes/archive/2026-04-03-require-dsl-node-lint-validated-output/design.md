## 上下文

目前 `dsl_node` 已经具备三块基础能力：它能通过 `create_agent` 生成 `TaskDocument`，能访问 `lint` 工具，也能消费 richer lint diagnostics。问题在于，仅靠“先用 `lint` 自检”的软提示还不够。真实 smoke 已经说明，模型往往只调用一次 `lint` 就结束，哪怕拿到了明确的 `invalid` 结果和修正模板。

这次变更要把现有能力组织成一个更硬的默认行为：`dsl_node` 必须把 `lint` 当作提交前检查工具；如果 `lint` 返回 `invalid`，必须继续修正并再次校验；整个过程受 `max_tool_calling` 预算约束；如果 agent 完全没调用 `lint`，Python 侧仍要做 fallback lint。

## 目标 / 非目标

**目标：**
- 强化 `dsl_node` 的默认 system/user prompt，明确要求在最终输出前使用 `lint` 做检查。
- 把“输出 `lint valid` 的 TaskDocument”写成 `dsl_node` 的默认目标。
- 明确 `dsl_node` 在看到 `lint invalid` 结果后，必须继续依据 `issues` 与 `expected` 修正 candidate。
- 为 `dsl_node` 提供有限的 `max_tool_calling` 预算，用于受控的多次 `lint` 校验。
- 保留 fallback lint，并把是否触发 fallback 作为可观察元数据暴露出来。
- 为 workflow 和 smoke 测试增加对应断言，确保这个行为契约不会回退。

**非目标：**
- 不修改 `response_format=TaskDocumentSchema` 的设计。
- 不新增 engine primitive 或改写 DSL shape catalog。
- 不要求这次变更就解决所有 Fireball 类 lowering 细节。

## 决策

### 决策 1：prompt 必须把 invalid 后继续修正写成硬约束

- 选择原因：当前的主要缺口不是工具不存在，而是模型在拿到 `invalid` 结果后仍会直接结束。只说“用 lint 检查”不够，必须把“invalid 就继续修”写成默认约束。
- 方案：在 `planner_dsl_node_system.txt` 和 `planner_dsl_node_user.txt` 中明确要求：
  - 在最终输出前使用 `lint` 检查 candidate
  - 最终目标是输出 `lint valid` 的 TaskDocument
  - 如果拿到 `invalid` 结果，不应把该 candidate 当作理想最终答案
  - 必须依据 `issues` 和 `expected` 继续修正并再次检查，直到通过或预算耗尽
- 替代方案：仍停留在“建议使用 lint”的软提示
- 未选择原因：已被 smoke 证明不足

### 决策 2：使用有限 `max_tool_calling`，而不是无限循环或重型外层状态机

- 选择原因：需要让 agent 有真正再次修正的机会，但又不能变成无限 tool 调用。
- 方案：为 `dsl_node` agent 设置有限的 `max_tool_calling` 预算，例如 3 次 `lint` 调用；保持 `response_format=TaskDocumentSchema` 不变。
- 替代方案：无限制依赖 agent 自发循环，或在 Python 层包一层重型外部状态机。
- 未选择原因：前者不可控，后者会重新引入实现复杂度和协议张力。

### 决策 3：保留 fallback lint，防止 agent 完全不调用工具

- 选择原因：即使 prompt 和预算都在，provider 或模型仍可能一次 tool 都不调。
- 方案：保留 `DslNode.run()` 的 fallback lint；如果 agent 没主动产出 lint 结果，节点补做至少一次 lint，并在元数据中记录 `used_fallback`。
- 替代方案：完全依赖 agent 自己调用 lint。
- 未选择原因：一旦 agent不调工具，整个“valid before submit”约束就失去最后兜底。

### 决策 4：测试必须观察多次 lint 和 fallback 信号

- 选择原因：如果只测 prompt 文本，很难知道真实行为是否前进。
- 方案：补 workflow 和 smoke 相关测试，断言：
  - prompt 明确要求 invalid 后继续修正
  - 节点配置了 `max_tool_calling`
  - fallback lint 仍可触发
  - smoke 输出能看到 `lint_calls`，必要时还能看到 `used_fallback`
- 替代方案：只人工看 smoke
- 未选择原因：回归风险高

## 风险 / 权衡

- [风险] 即使加了约束，模型仍可能在预算内没有修到 valid  
  - 缓解措施：让 prompt 明确消费 `issues` / `expected`，并在返回时保留最终 `lint_result`，便于继续分析失败点。

- [风险] 增加 tool 调用预算会拉长 smoke 延迟  
  - 缓解措施：把预算控制在小整数范围，例如 2-3 次，并继续保留独立的 fast smoke / unit tests。

- [风险] 过强的 prompt 约束可能导致模型在不确定时输出保守但不完整的 DSL  
  - 缓解措施：保持 richer diagnostics、canonical example 和现有 shape catalog 不变，让模型有足够具体的修正依据。

## Migration Plan

1. 更新 `dsl_node` 默认 prompt，加入“invalid 后继续修正”与“直到 valid 或预算耗尽”的约束。
2. 在 `DslNode.run()` 或 agent 装配层配置 `max_tool_calling`，允许受控的多次 `lint`。
3. 保留并强化 fallback lint 元数据，保证 smoke 可观察。
4. 更新 workflow / smoke 测试，覆盖多次 lint 与 fallback 场景。
5. 手动运行 `uv run src/smoke/test_dsl.py`，确认输出中能看见更真实的 lint 行为信号。

## Open Questions

- `max_tool_calling` 的默认预算应该是 2 还是 3？
- smoke 的人类可读输出是否也应增加 `used_fallback`，还是只保留在 JSON / `dsl_node_meta` 里？
