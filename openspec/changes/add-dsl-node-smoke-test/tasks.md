## 1. Smoke Entry

- [x] 1.1 新增 `src/smoke/test_dsl.py`，提供独立的 `dsl_node` smoke CLI 入口。
- [x] 1.2 让脚本默认读取 `output/test_task_draft.json`，并支持显式覆盖 draft 文件与配置文件路径。
- [x] 1.3 在脚本中读取并校验 `TaskDraft`，然后调用真实 `DslNode` 生成 `task_document` 和 `lint_result`。

## 2. Output Contract

- [x] 2.1 设计人类可读输出，至少展示 draft 文件路径、输入 instruction、生成的 DSL 和 lint 状态。
- [x] 2.2 增加 `--json` 模式，输出稳定的 `draft`、`task_document`、`lint_result` 结构。

## 3. Validation

- [x] 3.1 更新 `src/tests/test_smoke_scripts.py`，增加 `dsl_node` smoke 脚本的最小自动测试。
- [x] 3.2 在自动测试中 patch `DslNode.run` 或等价边界，避免绑定真实模型返回文案，同时验证脚本会读取默认样例并产出可解析结果。
- [x] 3.3 手动运行一次 `src/smoke/test_dsl.py` 或等价命令，使用 `output/test_task_draft.json` 检查输出 DSL 是否可观察。
