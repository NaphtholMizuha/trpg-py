## 为什么

当前 `task_node` 的提示词虽然已经强调 judgment-first，但仍可能把本应留给 `dsl node` 或 `engine` 处理的信息误判为 `missing_info`。特别是在涉及骰子、随机伤害、豁免结果等随机性数值时，第一阶段有时会把这些未来运行期才会产生的值当作缺失信息，导致 TaskDraft 过度保守。

## 变更内容

- 调整 `task_node` 提示词，让它明确知道后面还有 `dsl node` 和 `engine` 两个下游阶段。
- 在 prompt 中补充阶段职责边界：`task node` 负责描述执行意图与所需状态路径，`dsl node` 负责结构化翻译，`engine` 负责运行期求值与随机结果落地。
- 明确约束：骰子结果、随机伤害、攻击掷骰、豁免成败等运行期随机性数值不得写入 `missing_info`。
- 增加 few-shot 或规则示例，展示“未知随机结果”应保留在 judgments / execution plan 中，而不是当作缺失前置条件。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `planner-langgraph-workflow`: task_node 的提示词将新增对下游 `dsl node` 与 `engine` 阶段的职责感知，并收紧 `missing_info` 的使用边界，禁止把运行期随机性结果误判为缺失信息。

## 影响

- `config/prompts/planner_task_node_system.txt`
- `config/prompts/planner_task_node_user.txt`
- `src/tests/test_planner_workflow.py`
- 可能涉及 `src/smoke/test_task.py` 或相关 smoke / prompt 测试
