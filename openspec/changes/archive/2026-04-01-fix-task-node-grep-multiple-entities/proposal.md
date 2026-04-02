## 为什么

当前 `task_node` 在处理涉及多个实体（如主语+宾语）的 TRPG 指令时，grep 仅查询了主语（Aldera）的状态，而忽略了宾语（goblin）。这导致 LLM 在无证据的情况下直接编造目标路径（如 `actors.goblin.hp.current` 而非 `actors.goblin_1.hp.current`），违背了 "Do not invent exact paths" 的 prompt 约束。需要通过收紧 prompt 来强制 LLM 在执行 reads/writes 前，grep 所有相关实体。

## 变更内容

- 修改 `config/prompts/planner_task_node_system.txt`：
  - 在 "How to use grep well" 章节中新增一条明确约束：如果 judgments 涉及多个实体（actor、target、weapon、spell 等），必须对每个实体执行 grep，确认其确切路径后才能写入 reads 或 writes。
  - 在 "Judgment-to-path discipline" 中补充：涉及多目标时，必须逐一 grep 目标状态。
- 修改 `config/prompts/planner_task_node_user.txt`：
  - 在 requirements 中增加一条："When judgments involve multiple entities, grep each entity separately before finalizing reads or writes."
- （可选）更新 few-shot 示例：增加一个包含主语+宾语双实体查询的示例，展示 search → judgments → grep actor → grep target → bind paths 的完整流程。

## 功能 (Capabilities)

### 新增功能
- `task-node-state-binding`: 强制 task_node 在生成 reads/writes 前，对涉及的所有实体（主语、宾语、目标等）执行 grep 状态绑定，禁止在未证实的情况下编造路径。

### 修改功能
（无）

## 影响

- `config/prompts/planner_task_node_system.txt`
- `config/prompts/planner_task_node_user.txt`
- `src/smoke/test_task.py` 的测试输出（预期更准确的路径绑定和更少的假设）
