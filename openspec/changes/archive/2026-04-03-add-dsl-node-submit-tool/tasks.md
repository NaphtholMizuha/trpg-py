## 1. DslNode 输出协议

- [x] 1.1 保留 `dsl_node` 的 `response_format=TaskDocumentSchema`，移除默认外层 repair loop 与固定 lint 预算控制
- [x] 1.2 简化 `src/augury/planner/nodes/dsl_node.py` 的默认控制流，改为“工具可用 + 一次性结构化提交”
- [x] 1.3 清理与 `repair_mode/current_candidate/lint_calls/max_lint_calls` 绑定过深的节点状态和元数据

## 2. Prompt 调整

- [x] 2.1 重写 `planner_dsl_node_system.txt`，把 `lint` 改为诊断工具而不是强制控制流工具
- [x] 2.2 重写 `planner_dsl_node_user.txt`，删除默认 `repair_mode/current_candidate/lint_budget` 负担并保留与结构化输出兼容的输入形式
- [x] 2.3 删除或收紧与强制 repair 回路、固定 lint 预算绑定过深的提示词约束

## 3. 验证与观察

- [x] 3.1 更新 `src/tests/test_planner_workflow.py`，覆盖保留 `response_format` 后的简化控制流与 lint 诊断场景
- [x] 3.2 更新 `src/tests/test_smoke_scripts.py`，覆盖 `test_dsl` 在简化后的人类可读输出和 JSON 输出
- [x] 3.3 手动运行 `uv run src/smoke/test_dsl.py`，确认 `dsl_node` 在保留 `response_format` 时不再因强制 repair 提示词而报 `Extra data`
