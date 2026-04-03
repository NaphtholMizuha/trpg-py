## 为什么

当前 `task_node` 在处理 `Aldera用火球术攻击goblin` 这类范围法术时，仍会把任务误收窄成“对单个 goblin 做一次伤害结算”。这会导致 `TaskDraft` 漏掉范围覆盖、位置判定和法术环级绑定等关键前提，并让 smoke 看起来像“查到了规则”，实际却没有把任务结构理解完整。

## 变更内容

- 强化 `task_node` prompt，对具名法术要求先绑定法术身份，再绑定默认施法环级与对应法术位资源。
- 强化 `task_node` prompt，对 AoE / burst / line / cone 一类范围效果要求显式考虑施法距离、爆点或覆盖范围、以及受影响对象集合。
- 调整 `TaskDraft` 语义，使其能够诚实表达“先判定哪些对象被覆盖，再逐个结算”的任务结构，而不是默认降格成单目标攻击。
- 要求 `TaskDraft.evidence` 与 `states` 同时暴露与范围判定、法术环级绑定相关的关键规则 / 状态证据。
- 增加测试与 smoke 案例，验证 `Fireball` 默认绑定 3 环、不会误用 1 环法术位、并且会读取位置或在位置不足时显式暴露缺口。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `planner-langgraph-workflow`: task_node prompt 与 TaskDraft 契约将新增 AoE 覆盖判定、施法环级绑定和范围法术任务结构要求。
- `task-node-state-binding`: task_node 在范围法术或范围效果任务中，将必须绑定 actor / target 的位置等状态证据，而不是只绑定豁免与 HP 路径。

## 影响

- `config/prompts/planner_task_node_system.txt`
- `config/prompts/planner_task_node_user.txt`
- `src/augury/planner/task_document.py`
- `src/augury/planner/nodes/task_node.py`
- `src/tests/test_planner_workflow.py`
- `src/tests/test_smoke_scripts.py`
- `src/smoke/test_task.py`
