## 上下文

当前 `test_dsl` 的职责是：
- 读取 `TaskDraft`
- 调用真实 `DslNode`
- 打印 `task_document`
- 打印 `lint_result`

这对调 prompt 和 repair loop 很有帮助，但对“这份 DSL 是否真的可用”仍然只验证到一半。项目里已经有成熟的执行能力：
- `augury.execute_task(...)` 能执行 `TaskDocument`
- engine 本身通过 `augury.store` 读写状态
- `src/smoke/test_engine.py` 已经演示了如何构造确定性 state 和 dice roller

因此，这次设计不是发明新的执行框架，而是让 `test_dsl` 在保留现有输出的前提下，追加一个受控的执行阶段。

## 目标 / 非目标

**目标：**
- 让 `test_dsl` 在 `lint_result.status == "valid"` 时继续执行生成出的 `TaskDocument`。
- 让 `test_dsl` 使用真实 engine 和 store，而不是 fake executor。
- 让脚本输出包含执行状态和关键状态变化，证明生成 DSL 的运行效果。
- 保持 `test_dsl` 默认入口仍然面向单份 `TaskDraft` 样例，不把它扩展成完整 planner workflow smoke。

**非目标：**
- 不要求 `test_dsl` 覆盖所有 engine 规则场景。
- 不在这次变更里修复 Fireball 样例本身的所有 DSL 生成问题。
- 不把 `test_dsl` 和 `test_engine.py` 完全合并成同一个脚本。
- 不要求引入复杂的 diff 引擎；第一版只需要稳定、可读的关键变化摘要。

## 决策

### 决策 1：执行阶段只在 lint 通过后发生

- 选择原因：无效 DSL 的失败应该归因于 planner/lint，而不是 engine。先 lint 再执行能避免混淆问题来源。
- 方案：`test_dsl.py` 仅在 `lint_result.status == "valid"` 时调用 `execute_task(...)`。
- 替代方案：无论 lint 是否通过都尝试执行。
- 未选择原因：会让 smoke 结果同时混入 DSL 合法性问题和 runtime 问题，降低调试价值。

### 决策 2：复用真实 engine/store 路径，而不是新建 smoke 专用 executor

- 选择原因：用户明确希望证明“生成的 DSL 真的可以运行”。如果换成 mock executor，就无法证明这一点。
- 方案：直接复用 `augury.execute_task(...)`，并对执行前后的 state 做快照比较。
- 替代方案：实现一个只检查 step 形状的 fake runner。
- 未选择原因：那只能证明“看起来像能执行”，不能证明“真的能执行”。

### 决策 3：状态变化以摘要形式展示，而不是打印完整 world state

- 选择原因：完整 state 往往过大，不利于 smoke 观察。开发者真正关心的是哪些路径被改了、改成了什么。
- 方案：展示执行状态、关键 report 字段，以及执行前后发生变化的 path/value 摘要。
- 替代方案：总是打印整个 state JSON。
- 未选择原因：噪音太大，而且不利于最小自动测试做稳定断言。

### 决策 4：默认 fixture 优先复用现有 smoke world state 语义

- 选择原因：`test_dsl` 和其他 smoke 脚本已经围绕默认 world state fixture 协作；追加执行阶段时，应尽量保持同一套样例输入语义。
- 方案：优先读取配置中的 world state 文件，并在脚本内部转换成 engine 可消费的 state；必要时增加确定性 roller。
- 替代方案：为 `test_dsl` 单独发明一份新的执行样例 state。
- 未选择原因：会让 `TaskDraft`、`dsl smoke` 和 `engine smoke` 样例逐渐脱节。

## 风险 / 权衡

- [风险] 生成 DSL 虽然能 lint，但默认样例 world state 不足以执行
  - 缓解措施：在输出中明确区分 `lint_result` 与 `execution_result`，并允许展示执行失败原因。

- [风险] smoke 输出变长
  - 缓解措施：默认只展示执行摘要和变化路径；完整对象保留在 `--json` 模式里。

- [风险] `test_dsl` 与 `test_engine.py` 的 fixture 逐渐出现重复
  - 缓解措施：优先抽取共享辅助函数，而不是复制整段构造逻辑。

## Migration Plan

1. 为 `test_dsl.py` 增加执行阶段开关和输出结构。
2. 接入默认 world state fixture、engine `execute_task(...)` 和确定性 roller。
3. 为执行前后 state 生成最小变化摘要。
4. 更新 smoke 自动测试，覆盖 lint 通过后进入执行阶段、lint 失败时跳过执行阶段。
5. 用现有 `test_task_draft.json` 样例做一次真实手动验证。

## Open Questions

- `test_dsl` 是否应该默认执行，还是提供显式 `--execute` 开关更稳妥？
- 关键状态变化摘要是否只列出被改动的 path，还是也要附带 old/new 值？
- 当执行阶段依赖固定骰子结果时，是否应当允许从命令行传入预置骰序列？
