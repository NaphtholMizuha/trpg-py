## 上下文

当前 `dsl_node` 的默认实现同时依赖两套协议：
- agent 在内部通过 `lint` 工具做自检或修复；
- provider-native structured output 负责把最终响应解析成 `TaskDocumentSchema`。

这套组合在概念上本来是成立的，因为 `task_node` 已经证明了“工具 + `response_format`”是可以稳定共存的。真正的问题更像是：`dsl_node` 在 prompt 和代码层都被改成了带内部 repair 回路的控制流节点，prompt 里出现了 `repair_mode`、`current_candidate`、`latest_lint_result`、`lint_budget` 等状态，而 `lint` 也被规定成必须调用、限次调用、成功即停的流程控制器。

因此，这次变更不再动 `response_format=TaskDocumentSchema` 这条最终提交协议，而是把 `dsl_node` 拉回更接近 `task_node` 的工作方式：
- `lint` 只提供诊断信息；
- prompt 不再携带强制 repair 回路和多份中间状态；
- agent 最终仍以单次结构化提交交付 `TaskDocument`。

## 目标 / 非目标

**目标：**
- 保留 `dsl_node` 的 `response_format=TaskDocumentSchema` 最终提交协议。
- 让 `lint` 在 `dsl_node` 中回到“诊断/查证工具”角色，允许在提交前使用，但不再承担硬性的内部控制流职责。
- 保持 `dsl_node` 仍由 `langchain.create_agent` 驱动，外层 workflow 仍保持 `task_node -> dsl_node -> end`。
- 让 smoke 和测试能验证 agent 使用 `lint` 诊断后仍可继续稳定提交最终 DSL，并串接后续执行链路。

**非目标：**
- 不在这次变更里扩展 engine primitive 或 DSL 语义范围。
- 不在这次变更里完全移除 `lint`；它仍然保留为 `dsl_node` 可调用工具。
- 不在这次变更里移除 `response_format=TaskDocumentSchema`。
- 不在这次变更里引入新的 submit 工具或新的外层 workflow 节点。
- 不把 `dsl_node` 改回纯手写函数或绕过 agent。

## 决策

### 决策 1：保留 `response_format=TaskDocumentSchema` 作为最终交付协议

- 选择原因：`task_node` 已经证明工具和结构化输出可以稳定共存，因此当前问题不应再归因到 `response_format` 本身。保留它可以继续让 `dsl_node` 的最终提交边界清晰、类型严格。
- 方案：`src/augury/planner/nodes/dsl_node.py` 继续通过 `create_agent(..., response_format=TaskDocumentSchema)` 驱动最终提交，不引入新的本地文本解析协议。
- 替代方案：移除 `response_format`，改成本地 JSON 文本解析。
- 未选择原因：这会让 `dsl_node` 偏离当前成功工作的 `task_node` 模式，也和用户刚确认的设计决策冲突。

### 决策 2：`lint` 被定义为诊断工具，而不是强制控制流工具

- 选择原因：`task_node` 之所以稳定，是因为工具只负责提供信息；`dsl_node` 目前的脆弱性则来自把 `lint` 绑定成“必须驱动回路”的控制器。把 `lint` 降回诊断工具，agent 仍可以在提交前用它找错，但不会再被要求在普通 assistant 输出和原生 structured output 之间维持复杂回路状态。
- 方案：prompt 将要求 agent 可以在最终结构化提交前调用 `lint` 来检查 candidate，但 `lint` 是否使用以及使用几次由 agent 自主决定；代码侧不再额外维护固定 repair 预算和外层 while-loop。
- 替代方案：继续把 `lint` 视为必须调用、带预算、成功即停的流程控制器。
- 未选择原因：这会继续把 `dsl_node` 推向“内部控制流 + 最终原生 JSON”的混合模式，正是当前不稳定来源。

### 决策 3：移除外层 repair 回路和 prompt 中过重的状态负担

- 选择原因：当前最可疑的干扰项不是 structured output 本身，而是我们额外塞给 `dsl_node` 的 repair 状态和控制流。只要把这些状态拿掉，模型更可能像 `task_node` 那样在工具辅助后一次性提交结构化结果。
- 方案：`src/augury/planner/nodes/dsl_node.py` 不再默认在 Python 外层维护 `current_candidate`、`previous_lint_result`、`lint_calls_used`、`repair_rounds` 这样的回路状态；默认 prompt 也不再暴露这些字段。
- 替代方案：继续保留外层 repair loop，只靠 prompt 约束让它“别输出多余内容”。
- 未选择原因：这会继续让 `dsl_node` 带着一整套与 `task_node` 不同的交互负担。

### 决策 4：默认 prompt 必须强调“诊断后一次性结构化提交”

- 选择原因：即使保留 `response_format`，如果 prompt 仍然要求模型同时维护 repair 状态、预算和候选版本，它依然容易在一次响应中混入过多控制流痕迹。
- 方案：`dsl_node` 默认 prompt 必须明确规定：
  - `lint` 可以用来检查 candidate；
  - 最终必须一次性提交结构化 `TaskDocument`；
  - 不要在工具使用后继续输出 repair 说明、候选版本说明或额外控制流文本；
  - 不要把 `lint` 当作必须驱动回路的阶段控制器。
- 替代方案：只改代码，不改 prompt。
- 未选择原因：会保留当前“提示词仍在要求复杂回路”的主要不稳定来源。

### 决策 5：smoke 入口继续观察 lint 与执行结果，但不再突出 repair 元数据

- 选择原因：开发者仍然需要看到 `dsl_node` 生成的最终 TaskDocument、lint 结果和可执行性，但在这次改动后，`repair_used`、`repair_rounds`、`lint_calls/max_lint_calls` 不再是核心真相。
- 方案：`src/smoke/test_dsl.py` 继续展示 `task_document`、`lint_result`、`execution_result`、`state_changes`，但默认观察重点回到最终 DSL、lint 结论和运行结果。
- 替代方案：继续把 repair 元数据当作默认 smoke 观察核心。
- 未选择原因：这会和“去掉强制 repair 回路”方向冲突。

## 风险 / 权衡

- [风险] 去掉默认 repair 回路后，某些以前会自动修掉的问题可能重新暴露
  - 缓解措施：先优先恢复协议稳定性；如果后续确实需要更强自修，再重新设计更轻量的修复机制。

- [风险] `lint` 改成诊断工具后，模型可能选择少用或不用它
  - 缓解措施：在 prompt 里继续鼓励将 `lint` 作为提交前诊断手段，并通过 smoke 观察真实使用效果。

- [风险] 仅改 prompt 而不够改代码，可能会保留旧的回路状态干扰
  - 缓解措施：同步简化 `DslNode.run()` 的默认控制流，确保实现与 prompt 方向一致。

## Migration Plan

1. 保留 `dsl_node` 的 `response_format=TaskDocumentSchema` 配置。
2. 简化 `dsl_node` 的默认控制流，移除外层 repair loop 与固定 lint 预算状态。
3. 重写 `dsl_node` prompt，把 `lint` 改成诊断工具说明，删除 `repair_mode/current_candidate/lint_budget` 这类重状态输入。
4. 更新 workflow 测试和 smoke 测试，验证：
   - 保留 `response_format` 后仍能稳定得到最终结构化 `TaskDocument`；
   - `lint` 可以作为诊断工具使用；
   - smoke 可以继续观察 lint 和 engine 执行链路。

## Open Questions

- 如果后续仍需要 repair，应该做成更轻量的 agent 内部习惯，还是保留单独的可选实验路径？
- smoke 是否还需要显示 `lint` 调用次数，还是只看最终 lint 结论就够？
