## 1. TaskDraft 契约

- [ ] 1.1 为 `TaskDraft.missing_info` 设计结构化条目，至少包含缺口描述、默认值或默认处理、以及缺口原因。
- [ ] 1.2 调整相关序列化与测试辅助，确保 `missing_info` 的默认值语义对 `dsl_node` 可直接观察。

## 2. DSL Node Prompting

- [ ] 2.1 更新 `config/prompts/planner_dsl_node_system.txt`，明确 `dsl_node` 只翻译 `TaskDraft`，不得重新补完任务结构。
- [ ] 2.2 更新 `config/prompts/planner_dsl_node_user.txt`，要求直接消费 `missing_info` 的默认值语义，而不是自行猜测默认处理。
- [ ] 2.3 为 `dsl_node` 增加 few-shot，并按 `task_node` 已定义的任务类型原型组织示例。

## 3. Validation

- [ ] 3.1 更新 `src/tests/test_planner_workflow.py`，断言 `dsl_node` prompt 已明确声明“只翻译、不补完”的边界。
- [ ] 3.2 增加测试，验证 `TaskDraft.missing_info` 已包含默认值语义，且 `dsl_node` 可以直接消费。
- [ ] 3.3 增加 prompt 测试，验证 `dsl_node` few-shot 与 `task_node` 的任务类型原型对齐。
