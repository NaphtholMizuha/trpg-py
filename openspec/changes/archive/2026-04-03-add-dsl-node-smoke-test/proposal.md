## 为什么

现在仓库已经有 `task_node` 的独立 smoke 入口，但 `dsl_node` 仍然只能通过 `test_planner_workflow.py` 里的 fake agent / fake document 间接观察。这样虽然能约束装配与 prompt 传递，却看不到“给定一个真实 `TaskDraft`，当前 `dsl_node` 会翻译出什么 DSL”。

你已经给出了一个很适合固定观察的输入样例：`output/test_task_draft.json`。把它接成一个独立 smoke 入口后，开发者就能在改 prompt、模型或 lint 规则时，直接检查生成的 `TaskDocument` 是否还合理，而不是先手工拼装 Python 片段。

## 变更内容

- 新增一个独立的 `dsl_node` smoke 脚本入口，默认读取 `output/test_task_draft.json` 作为输入。
- 让该脚本构造真实 `DslNode` 与真实 `lint_tool`，输出生成的 DSL 结果以及 lint 结论。
- 为脚本增加人类可读模式与 `--json` 模式，便于人工检查与最小自动验证。
- 增加对应自动测试，约束脚本参数、输入读取、输出结构与默认样例路径。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `smoke-test-layout`: 在 `src/smoke/` 下补充 `dsl_node` 的独立手动验证入口，并明确其默认输入样例、输出契约与最小自动测试要求。

## 影响

- `src/smoke/test_dsl.py`
- `src/tests/test_smoke_scripts.py`
- `output/test_task_draft.json` 作为默认 smoke 输入样例
- 可能涉及 `src/augury/planner/nodes/dsl_node.py` 的装配辅助复用，但不改变其核心职责
