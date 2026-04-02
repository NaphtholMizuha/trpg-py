## 1. Smoke Script

- [x] 1.1 新增 `src/smoke/test_task.py`，按现有 smoke 脚本风格提供 `task_node -> TaskDraft` 的手动运行入口。
- [x] 1.2 为脚本增加默认 instruction、`--instruction` 参数和 `--state-file` 参数，并让它们真正驱动 `TaskNode` 输入。
- [x] 1.3 在脚本中装配真实 `TaskNode` 及其所需工具和配置，确保它输出真实 `TaskDraft` 结果而不是静态样例。

## 2. Output Contract

- [x] 2.1 实现人类可读输出，展示 `task`、`reads`、`judgments`、`writes`、`missing_info`、`assumptions` 等关键字段。
- [x] 2.2 实现 `--json` 输出，确保脚本能输出可解析且完整反映 `TaskDraft` 的 JSON 结果。

## 3. Validation

- [x] 3.1 新增或更新自动测试，验证 `src/smoke/test_task.py` 可以成功运行并返回预期退出码。
- [x] 3.2 新增或更新自动测试，验证 `--json` 输出可解析且包含 `TaskDraft` 关键字段。
