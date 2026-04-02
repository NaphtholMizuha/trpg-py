## 为什么

现在 `task_node` 已经开始稳定地产出更诚实的 `TaskDraft`，但 `dsl_node` 仍然几乎没有清晰的翻译边界。尤其是 `missing_info` 如果没有默认值语义，`dsl_node` 很容易重新做理解、补完甚至自行推断，破坏“两阶段中间对象作为真相”的设计目标。

## 变更内容

- 收紧 `TaskDraft.missing_info` 的语义，要求其条目带有默认值或默认处理方向，使下游可以直接翻译而不是重新发明补全逻辑。
- 明确 `dsl_node` 的职责是把 `TaskDraft` 翻译成 `TaskDocument`，而不是重新理解任务、补全场景或覆盖 `task_node` 的判断。
- 调整 `dsl_node` prompt，要求其直接消费 `task`、`judgments`、`reads`、`writes`、`missing_info`、`evidence` 与 `states`，并把 `missing_info` 的默认值语义翻译进 DSL。
- 为 `dsl_node` 增加 few-shot，并要求其场景原型直接复用 `task_node` 已定义的任务类型原型，而不是单独发明另一套分类体系。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `planner-langgraph-workflow`: `dsl_node` 将被约束为纯翻译阶段，`missing_info` 将新增默认值语义，且 `dsl_node` few-shot 需复用 `task_node` 的任务类型原型。

## 影响

- `src/augury/planner/task_document.py`
- `src/augury/planner/nodes/dsl_node.py`
- `config/prompts/planner_dsl_node_system.txt`
- `config/prompts/planner_dsl_node_user.txt`
- `src/tests/test_planner_workflow.py`
- 可能涉及 `src/tests/test_smoke_scripts.py`
