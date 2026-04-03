## 1. TaskDraft Schema

- [x] 1.1 为 `TaskDraft` 增加 `evidence` 字段，并明确其用于承载摘要化证据而不是原始规则原文。
- [x] 1.2 删除 `TaskDraft.read_values` 字段，避免继续保留重复读值快照。
- [x] 1.3 将 `TaskDraft.context_lines` 重命名为 `states`，明确其承载状态证据。
- [x] 1.4 调整相关序列化与 smoke 输出，使 `evidence` 与 `states` 都成为稳定可观察字段。

## 2. Task Node Prompting

- [x] 2.1 更新 `config/prompts/planner_task_node_system.txt`，要求 `task_node` 把有用规则或关键状态事实摘录进 `evidence`。
- [x] 2.2 更新 `config/prompts/planner_task_node_user.txt`，明确 `evidence` 是给后续阶段消费的证据摘录，而不是调查日志或全文复制。
- [x] 2.3 增加 few-shot，示范 Fireball 类案例如何把范围、豁免和伤害规则摘录到 `evidence`。

## 3. Validation

- [x] 3.1 更新 `src/tests/test_planner_workflow.py`，断言 TaskDraft / task_node prompt 已包含 `evidence` 与 `states` 语义。
- [x] 3.2 更新 smoke 或相关测试，验证 `Aldera用火球术攻击goblin` 这类案例的 `TaskDraft` 会输出有用的 `evidence` 摘录。
- [x] 3.3 增加测试，验证 `evidence` 放的是摘要化证据而不是整段规则原文。
- [x] 3.4 增加测试，验证 `TaskDraft` 不再暴露 `read_values`，且状态证据字段已从 `context_lines` 迁移为 `states`。
