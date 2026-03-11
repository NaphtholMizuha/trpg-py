请执行以下任务:

任务ID: {task_id}
任务描述: {natural_description}
行动者: {actor}
目标: {target}
动作: {action}
DM批注: {dm_notes}

任务详情:
{raw_description}

工作流程：
1. 从task.context获取相关状态信息（Planner已提供）
2. 如有DM批注，请优先考虑批注中的指示
3. 使用evaluate执行掷骰和计算
4. 根据结果生成字段级变更指令（FieldChange格式）
5. 使用write_fields工具将变更写入KV状态
6. 检测简单连锁条件（HP归零、爆炸、坍塌）
7. 输出JSON格式的执行结果

重要：
- 攻击未命中时field_changes设为空数组
- 使用write_fields工具直接写入状态（不再由独立节点处理）
- new_value必须是完整的自然语言段落
- 输出必须是JSON格式，包含success, narration, field_changes, triggered_chains字段
- **连锁判断**: 根据执行结果判断是否需要触发连锁
  * 检查状态变化是否符合连锁条件
  * 考虑DM批注：如果DM批注明确说明不需要某连锁（如"不需要死亡豁免"），则不触发
  * 如果无连锁，triggered_chains设为空数组 []

输出JSON格式示例：
```json
{{"success": true,
  "narration": "攻击命中，造成10点伤害...",
  "field_changes": [{{"key": "Goblin.combat", "field": "HP", "old_value": "10/10", "new_value": "0/10", "operation": "MOD"}}],
  "triggered_chains": [{{"type": "death", "description": "哥布林HP降至0，触发死亡连锁", "source_key": "Goblin.combat", "priority": 100}}]
}}
```
注意：外层花括号是JSON语法，实际输出时不需要双花括号。
