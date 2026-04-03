## 为什么

当前 `task_node` 在 rule-first 任务中即使已经搜到了有用规则，也只能把结论硬塞进 `task`、`judgments` 或 `context_lines`。同时，现有 `read_values` 与 `context_lines` 的职责也不够清晰：一个重复暴露读值，一个名字又像“上下文杂项”而不是明确的状态证据。这使得中间对象缺少一份清晰的证据摘要，也让 smoke 难以观察 `task_node` 到底抓到了哪些真正有用的规则线索。

## 变更内容

- 为 `TaskDraft` 增加 `evidence` 字段，用于承载 `task_node` 认为对后续阶段有用的证据摘录。
- 删除 `TaskDraft.read_values` 字段，避免继续把读取结果以重复映射方式保留在中间对象里。
- 将 `TaskDraft.context_lines` 重命名为 `states`，明确它承载的是状态证据而不是泛化“上下文”。
- 明确 `evidence` 允许包含两类摘要化证据：
  - 规则证据，如从 search 结果提炼出的规则摘要
  - 规则所需的关键状态证据，如对当前绑定路径和关键状态事实的简短摘录
- 要求 `task_node` 只放经过摘录的证据，不直接塞入长段规则原文。
- 增加 few-shot 与 smoke / prompt 测试，验证 `Aldera用火球术攻击goblin` 这类案例会产出有用的 `evidence` 摘录。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `planner-langgraph-workflow`: TaskDraft 将新增 `evidence` 字段、删除 `read_values`、并把 `context_lines` 重命名为 `states`，要求 task_node 通过摘要化证据暴露其已确认的关键规则或状态线索。

## 影响

- `src/augury/planner/task_document.py`
- `src/augury/planner/nodes/task_node.py`
- `config/prompts/planner_task_node_system.txt`
- `config/prompts/planner_task_node_user.txt`
- `src/tests/test_planner_workflow.py`
- 可能涉及 `src/tests/test_smoke_scripts.py` 与 `src/smoke/test_task.py`
