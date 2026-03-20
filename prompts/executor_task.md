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
6. 优先把结果拆进三个字段：
   - `resource_costs`: 行动成本，例如法术位消耗、反应消耗、次数消耗
   - `primary_effects`: 本动作直接成立的主要结果，例如伤害、治疗、AC变化、状态变化
   - `contingent_effects`: 依赖前置结果才成立的附带结果，例如“若命中则附加状态”“若法术成功则后续效果”
7. `path` 必须写成字段级 `Key.Field`，例如 `Aldera.combat.HP`、`Aldera.equipment.护甲`、`Malik.spell_slots.1环`
8. 不允许整 key 覆盖；不要返回 `Aldera.combat` 或 `Malik.spell_slots` 这种 path
9. 优先遵循 planner 给出的 `执行步骤` 和 `预期写回`
10. 只能写入任务上下文中已经出现过的 `[KV ...]` 基础 key；`预期写回` 只是提示，不是唯一合法路径
11. `old_value` / `new_value` 都应该是字段值，不是整段 KV 文本
12. 不要调用任何写入工具
13. `field_changes` 可留空；如果填写，应等于以上三类变更的合并视图
14. 如果没有形成新的既成事实，可以返回空变更
