请执行以下任务:

任务ID: {task_id}
任务描述: {description}
执行步骤:
{execution_steps}
预期写回:
{write_targets}
行动者: {actor}
目标: {target}
DM批注: {dm_notes}

任务上下文:
{context}

写回键提示:
{key_hints}

要求:
1. 将这个任务视为当前这一轮唯一需要执行的一步
2. 只处理已经能落地的事实，不要扩写计划
3. 只有在需要掷骰、随机结果时才调用 `evaluate`
4. 不要用 `evaluate` 读取 KV、解析 `4/4` 这类字符串、或做简单减法；这些请直接根据上下文完成
5. 同一个随机量只调用一次 `evaluate`，得到结果后直接复用
6. 只返回字段级 `field_changes`，`path` 必须写成 `Key.Field`，例如 `Aldera.combat.HP`、`Aldera.equipment.护甲`、`Malik.spell_slots.1环`
7. 不允许整 key 覆盖；不要返回 `Aldera.combat` 或 `Malik.spell_slots` 这种 path
8. 优先遵循 planner 给出的 `执行步骤` 和 `预期写回`
9. 只能写入任务上下文中已经出现过的 `[KV ...]` 基础 key，且最好命中 `预期写回`
10. `old_value` / `new_value` 都应该是字段值，不是整段 KV 文本
11. 不要调用任何写入工具
12. 如果没有形成新的既成事实，可以返回空变更
