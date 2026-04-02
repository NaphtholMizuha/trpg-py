## 为什么

当前变更把 `task_node` 设计成“先生成 `query_plan`，再执行 grep，再起草 `TaskDraft`”的分段式流程。但实际探索表明，这种拆分会切断第一阶段的推理闭环：

- 查询规划 agent 不知道真实检索结果
- 起草 agent 没有工具权，只能消费别人筛过的上下文
- 像法术、规则依赖较强的任务很容易卡在“先规划、后起草”的边界上

现在需要把这个变更改写为更直接的一体式设计：`task_node` 保持单节点单 agent，由它自己在 ReAct 过程中决定如何使用工具，并最终只保留它认为合适的 `context` 进入 `TaskDraft`。

## 变更内容

- 删除把 `query_plan` 作为 `TaskDraft` 中间产物公开保留的要求。
- 删除“`task_node` 必须先显式生成查询计划再执行 grep”的约束。
- 要求 `task_node` 保持为单一 agent 节点，由同一个 agent 负责检索、思考和起草任务稿。
- 要求 `task_node` 最终只保留它认为适合支持任务稿的 `context_lines`，而不是暴露查询轨迹。
- 继续保留两项收敛要求：
  - 查询执行不得依赖过低固定 grep limit
  - `context_lines` 必须经过相关性筛选

## 功能 (Capabilities)

### 修改功能
- `planner-task-query-planning`: 从“显式 query plan 能力”调整为“task_node 自主检索并保留合适 context 的能力”。
- `planner-langgraph-workflow`: 第一阶段节点恢复为单一 `task_node` agent，不再在内部拆成“查询规划 + 起草”两个阶段。

## 影响

- 受影响代码：`src/augury/planner/nodes/task_node.py`、`TaskDraft` schema、相关 smoke 与测试。
- 受影响 prompt：`task_node` prompt 需要从“先写 query plan”改为“自主使用工具并产出任务稿”。
- 受影响可观察性：调试重点从“看 query_plan”转为“看最终保留下来的 `context_lines` 是否足够且相关”。
