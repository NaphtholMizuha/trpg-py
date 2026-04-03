## 1. Prompt 约束

- [x] 1.1 更新 `planner_dsl_node_system.txt`，明确要求在最终输出前使用 `lint` 检查 candidate
- [x] 1.2 更新 `planner_dsl_node_system.txt`，明确把输出当前 `lint` 视角下的 `valid` TaskDocument 作为默认目标
- [x] 1.3 更新 `planner_dsl_node_user.txt`，明确 `lint invalid` 时必须继续依据 `issues` 与 `expected` 修正 candidate
- [x] 1.4 更新 prompt，明确继续调用 `lint`，直到结果为 `valid` 或达到工具预算上限

## 2. Node 与测试契约

- [x] 2.1 调整 `src/augury/planner/nodes/dsl_node.py`，为 agent 配置有限的 `max_tool_calling`
- [x] 2.2 保留并扩展 fallback lint 元数据，记录 `used_fallback` 与最终 `lint_calls`
- [x] 2.3 更新 `src/tests/test_planner_workflow.py`，覆盖 `invalid -> 修正 -> 再 lint` 与 fallback 场景
- [x] 2.4 更新 `src/tests/test_smoke_scripts.py` 或等价测试，覆盖 smoke 可观察到 `lint_calls` 与 fallback 信号的场景

## 3. 验证

- [x] 3.1 运行相关单元测试，确认 `dsl_node` prompt 契约与工具预算逻辑未回退
- [x] 3.2 手动运行 `uv run src/smoke/test_dsl.py`，检查输出是否反映多次 `lint` 或 fallback 行为
