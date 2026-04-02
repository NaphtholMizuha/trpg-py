## 1. Prompt 修改

- [x] 1.1 在 `config/prompts/planner_task_node_system.txt` 的 "How to use grep well" 和 "Judgment-to-path discipline" 章节中，新增多实体 grep 的强制约束。
- [x] 1.2 在 `config/prompts/planner_task_node_user.txt` 的 requirements 中，增加一条关于多实体 grep 的硬性规则。
- [x] 1.3 （可选）在 system prompt 的 few-shot 示例中增加一个主语+宾语双实体查询的示例。

## 2. 验证

- [x] 2.1 运行 `uv run src/smoke/test_task.py --instruction "Aldera用火球术攻击goblin"`，检查 reads/writes 是否不再包含编造的 `actors.goblin.*` 路径，而是使用实际状态中的 `actors.goblin_1.*` 路径（或通过 missing_info 正确反映不确定性）。
