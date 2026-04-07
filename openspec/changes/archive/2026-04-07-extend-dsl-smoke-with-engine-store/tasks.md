## 1. DSL Smoke Execution Path

- [x] 1.1 扩展 `src/smoke/test_dsl.py`，让它在 `lint_result.status == "valid"` 时继续调用真实 engine 执行生成的 `TaskDocument`。
- [x] 1.2 为 `test_dsl` 接入默认 world state/store 输入，并补充确定性 roller 或等价执行控制，保证 smoke 结果稳定可观察。
- [x] 1.3 为 `test_dsl` 增加执行结果和关键 state 变化摘要输出，同时在 lint 未通过时显式跳过执行阶段。

## 2. Shared Fixtures And Output Contract

- [x] 2.1 复用或抽取 `test_engine.py` 中适合 `test_dsl` 的 state / execution 辅助逻辑，避免重复复制执行样例。
- [x] 2.2 更新 `--json` 输出契约，使其同时包含 `draft`、`task_document`、`lint_result`、`execution_result` 和状态变化摘要或等价字段。

## 3. Validation

- [x] 3.1 更新 `src/tests/test_smoke_scripts.py`，覆盖 lint 通过后进入执行阶段并输出执行结果的路径。
- [x] 3.2 更新 `src/tests/test_smoke_scripts.py`，覆盖 lint 失败时跳过执行阶段的路径。
- [ ] 3.3 用现有 `output/test_task_draft.json` 样例手动运行 `src/smoke/test_dsl.py`，确认该入口能够展示 DSL、lint、执行结果与状态变化摘要。
