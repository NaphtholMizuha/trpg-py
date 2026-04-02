## 为什么

当前 `task_node` 即使已经会先 `search` 再 `grep`，仍然经常出现 `judgments`、`reads`、`writes` 三者不对齐的问题。现在需要把提示词顺序进一步明确成一个稳定的内部过程：先可选 `search`，再先写出 `judgments`，再用 `grep` 去绑定 `reads`、`writes`、`missing_info` 和 `assumptions`。

## 变更内容

- 明确 `task_node` 提示词中的内部顺序：可选 `search` -> 生成 `judgments` -> 使用 `grep` 绑定 state paths。
- 要求 `reads`、`writes`、`missing_info` 和 `assumptions` 都必须围绕已经形成的 `judgments` 来补齐，而不是与 `judgments` 平行自由生成。
- 加强 `task_node` prompt 对 judgment/read/write 对齐关系的约束。
- 更新 few-shot，使其体现这种 judgment-first 的生成顺序。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `planner-langgraph-workflow`: `task_node` 的提示词顺序和中间推理约束发生变化，要求先形成 judgments，再绑定 reads/writes/missing_info/assumptions。

## 影响

- 受影响 prompt：`config/prompts/planner_task_node_system.txt`、`config/prompts/planner_task_node_user.txt`
- 受影响行为：`task_node` 产生的 `TaskDraft` 应更容易保持 judgments、reads、writes 的语义闭包
- 受影响测试：与 planner smoke / prompt 行为相关的测试和示例
