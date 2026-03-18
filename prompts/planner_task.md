DM指令: {user_input}

请分析 DM 指令，并规划“当前这一轮真正要执行的一步”。

约束：
- 使用工具查询需要的信息（`fetch_keys` / `read` / `search`）
- 输出必须保持 JSON 结构化，并映射为下面这些字段：
  - `task_id`
  - `description`
  - `action_type`
  - `actor`
  - `target`
  - `raw_query_appendix`
  - `context`
  - `execution_steps`
  - `write_targets`
- 将关键状态、规则依据和本轮真正要执行的一步整理进 `context`
- 同时输出结构化的 `execution_steps`，明确告诉 executor 如何判定、如何处理结果、如何写回
- 同时输出 `write_targets`，列出本轮预期会写入的字段级路径，例如 `Goblin.combat.HP`
- 只处理当前这一轮，不要补写后续轮次的计划
- `context` 必须是给 executor 直接消费的完整上下文
- 所有关键数值必须标明来源（KV/RAG/确认）
- `context` 必须写出精确的 world-state key，例如 `[KV Malik.spell_slots]`、`[KV Aldera.combat]`
- 如果 executor 需要写状态，`context` 必须给出当前旧值，并让 executor 能推导出字段级修改
- `KV` 信息要保留原始值，不要自行改写、压缩或二次解释
- `RAG` 信息要写成归纳后的规则结论，不要把长段检索原文直接塞进 `context`
- `actor` / `target` 必须优先使用 world-state 的英文 key root，例如 `Malik` / `Aldera`，不要填写中文名
- 不要只写“艾尔德拉受伤”这种自然语言，必须写清楚会影响哪个 key
- 只在缺少外部事实、DM裁定或玩家选择时，才允许在 `context` 中标记 `[Needs Confirmation]`
- 命中判定、伤害掷骰、豁免、检定、已知规则计算等属于 executor 可解决的内容，planner 不得把它们上抛给 DM
- 每个 `[Needs Confirmation]` 都必须同时给一个默认选项，格式为 `[Needs Confirmation] [Default: ...] 问题描述`

请将你熟悉的文本分区格式压缩成最小 JSON 字段：

- `action_type` 对应“行动类型”
- `context` 吸收“上下文信息 + 执行说明”中的执行所需内容
- `execution_steps` 保留真正的分步执行逻辑
- `write_targets` 保留预期写回字段
- `raw_query_appendix` 对应“原始查询附录”
  - 每项直接保留原始 KV / RAG 片段字符串

推荐的 `context` 结构：
- `【动作】...`
- `【可写状态】[KV Malik.spell_slots] 1环: 4/4 | 2环: 3/3`
- `【可写状态】[KV Aldera.combat] HP: 44/44 | AC: 18 | 反应: 可用`
- `【规则依据】[RAG 魔法飞弹] 归纳: 1环造成 3d4+3 力场伤害，自动命中`
- `【本轮可执行】...`
- `【待确认】[Needs Confirmation] [Default: 按最保守解释继续执行] ...`

推荐的 `execution_steps` 结构：
- `确认采用哪条默认裁定或既成事实`
- `进行哪一个判定 / 掷骰`
- `如何根据结果计算字段新值`
- `把哪个字段写回到哪个 path`

`raw_query_appendix` 推荐格式示例：
- `[KV] Aldera.combat: HP: 44/44 | AC: 18 ...`
- `[KV] Goblin.combat: HP: 10/10 | AC: 15 ...`
- `[RAG] 攻击规则: 进行攻击检定，命中后掷伤害`

请开始分析。
