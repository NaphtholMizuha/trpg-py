## 1. Prompt 约束

- [x] 1.1 更新 `config/prompts/planner_task_node_system.txt`，要求具名法术先绑定法术身份与默认施法环级，再绑定对应法术位资源。
- [x] 1.2 更新 `config/prompts/planner_task_node_system.txt`，要求 AoE / burst / line / cone 任务先表达覆盖范围与受影响对象集合，再表达逐对象结算。
- [x] 1.3 更新 `config/prompts/planner_task_node_user.txt`，明确缺失爆点、位置或默认环级时必须进入 `missing_info`，不得退化成看似完整的单目标计划。
- [x] 1.4 将 task_node few-shot 重组为约 5-6 个任务类型原型，至少覆盖单体攻击、单体法术、范围法术、治疗/增益、状态效果、纯查询等主要类别。
- [x] 1.5 在范围法术 few-shot 中示范位置读取、覆盖判定和 `evidence` / `states` 如何共同支撑任务稿。
- [x] 1.6 确保 few-shot 不直接复用 `火球术 Fireball`，避免 smoke / eval 样例污染。

## 2. TaskDraft 与 task_node 语义

- [x] 2.1 调整 `TaskDraft` 相关说明或字段注释，明确其需要支持“先判定覆盖对象，再逐个结算”的范围法术任务结构。
- [x] 2.2 调整 `src/augury/planner/nodes/task_node.py` 的后处理或轻量校验，避免范围法术在缺少位置前提时仍表现得像完整的单目标任务稿。
- [x] 2.3 调整 `TaskDraft.evidence` 与 `states` 的可观察输出，确保法术环级绑定和位置前提不会在 smoke 中被吞掉。

## 3. 验证

- [x] 3.1 更新 `src/tests/test_planner_workflow.py`，断言 task_node prompt 已包含默认环级绑定、AoE 覆盖判定与缺口暴露语义。
- [x] 3.2 更新 `src/tests/test_planner_workflow.py`，验证 Fireball 类任务不会再把 `level_1` 法术位错误绑定为默认资源路径。
- [x] 3.3 更新 smoke 或相关测试，验证 Fireball 类任务会读取 actor / target 位置，或在位置不足时把覆盖缺口写入 `missing_info`。
- [x] 3.4 更新 smoke 输出断言，验证 `evidence` 与 `states` 可观察到范围、豁免、伤害、法术环级和位置前提。
- [x] 3.5 增加 prompt 测试，验证 few-shot 已覆盖主要任务类型原型。
- [x] 3.6 增加 prompt 测试，验证范围效果 few-shot 展示了位置获取步骤，且不直接包含 `火球术 Fireball` 示例。
