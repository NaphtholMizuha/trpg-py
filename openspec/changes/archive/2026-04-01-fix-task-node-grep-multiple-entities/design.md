## 上下文

当前 `task_node` 的 system prompt 要求 LLM 在生成 reads/writes 前用 grep 绑定路径，但在实际运行中（如 `Aldera用火球术攻击goblin`），LLM 只 grep 了主语 Aldera 的状态（`spell_slots`、`spell_dc`），而未对宾语 goblin 执行任何 grep，导致直接编造了 `actors.goblin.hp.current` 等路径。实际状态中的 key 是 `goblin_1`，且豁免路径为 `abilities.dex.save`。

## 目标 / 非目标

**目标：**
- 收紧 prompt，明确强制 LLM 在 judgments 涉及多个实体时，必须对每个实体分别 grep。
- 更新 user prompt requirements，体现多实体 grep 的强制顺序。
- （可选）在 few-shot 示例中展示主语+宾语的双实体查询流程。

**非目标：**
- 修改 task_node 的代码逻辑或工具接口。
- 引入新的自动化验证层（如运行时检查每个 read/write 是否都有 grep 证据）。
- 修改世界状态的数据结构或字段命名规范。

## 决策

- **只改 prompt，不改代码**：当前 tool 调用已经完备，问题出在 prompt 对 LLM 行为的约束力不足。增加显式约束比写代码后校验更轻量。
- **在 system prompt 的 "How to use grep well" 和 "Judgment-to-path discipline" 两处同时强调**：前者告诉 LLM "怎么做"，后者告诉 LLM "不做会有什么后果"（路径进入 missing_info）。
- **在 user prompt requirements 里加一条硬性规则**：确保每次模型收到 requirements 列表时都能再次看到这条约束。

## 风险 / 权衡

- **[风险] LLM 仍可能忽略新约束 → [缓解措施]** 增加一个包含双实体查询的 few-shot 示例，用模式匹配强化行为。
- **[风险] 过度约束导致 LLM 发起过多 grep 查询 → [缓解措施]** prompt 明确指出 "only for entities that appear in your judgments"，避免对无关实体发起查询。
