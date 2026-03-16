请执行以下任务:

任务ID: {task_id}
任务描述: {description}
行动者: {actor}
目标: {target}
DM批注: {dm_notes}

任务详情:
{context}

执行上下文（仅能依据这里给出的状态快照判断，不得臆测未提供事实）:
{execution_context}

工作流程（严格执行）：

**STEP 1: 读取任务信息**
- 从 `task.context` 获取相关状态信息
- 从 `执行上下文` 获取当前任务允许使用的状态快照
- 如有 DM 批注，请优先考虑批注中的指示

**STEP 2: 判断任务模式**
- 如果 `task.task_category == "decision_response"`：
  这是一个响应动作。请输出：
  - `direct_changes`: 这个响应动作自己立即造成的状态变化
  - `resolution_effects`: 这个响应动作对原任务结算的修正
  - `consequence_changes`: 通常为空数组
  - `decision_points`: 通常为空数组
- 否则：
  这是一个普通任务。请输出：
  - `direct_changes`: 立即发生的变化，如法术位消耗、资源消耗、状态建立
  - `consequence_changes`: 要到 `apply_consequence` 阶段才落地的结果，如伤害、状态改变、理智损失
  - `decision_points`: 可以在某个 timing 被触发的决策窗口
  - `resolution_effects`: 普通任务通常为空数组

**STEP 3: 使用 evaluate 执行掷骰和计算**

**STEP 4: timing 规则**
`decision_points` 的 `timing` 必须使用以下标准值之一：
- `before_action`
- `before_resolution`
- `before_consequence`
- `after_consequence`
- `after_action`

**STEP 5: 检测简单连锁条件（HP归零、爆炸、坍塌）**

**STEP 6: 输出 JSON 格式结果**

绝对规则：
1. `direct_changes` 只放立即生效的变化
2. `consequence_changes` 只放延后到结果阶段生效的变化
3. 当前 `resolution_effects` 只支持一种效果：`{{"effect_type": "negate_consequence"}}`
4. 如果响应动作会阻止当前结果阶段生效，必须通过 `resolution_effects` 输出 `negate_consequence`
5. 不要把“对原动作的修正”直接写进响应动作自己的 `direct_changes`
6. 角色是否会某个能力、是否有反应可用、是否有法术位，必须以 `执行上下文` 为准；如果上下文没给出，明确写需要确认，不要擅自断言
7. 输出必须是 JSON，包含：
   - `success`
   - `narration`
   - `direct_changes`
   - `consequence_changes`
   - `decision_points`
   - `resolution_effects`
   - `triggered_chains`

输出示例 1：普通动作

```json
{{
  "success": true,
  "narration": "攻击命中，即将造成10点伤害",
  "direct_changes": [],
  "consequence_changes": [
    {{"path": "Goblin.combat.HP", "old_value": "10/10", "new_value": "0/10", "operation": "MOD"}}
  ],
  "decision_points": [],
  "resolution_effects": [],
  "triggered_chains": [
    {{"type": "death", "description": "哥布林HP降至0，触发死亡连锁", "source_key": "Goblin.combat"}}
  ]
}}
```

输出示例 2：带决策窗口的普通动作

```json
{{
  "success": true,
  "narration": "马利克施放魔法飞弹（1环），3发飞镖射向艾尔德拉",
  "direct_changes": [
    {{"path": "Malik.spells.1环法术位", "old_value": "4/4", "new_value": "3/4", "operation": "MOD"}}
  ],
  "consequence_changes": [
    {{"path": "Aldera.combat.HP", "old_value": "44/44", "new_value": "37/44", "operation": "MOD"}}
  ],
  "decision_points": [
    {{
      "decider": "艾尔德拉",
      "timing": "before_consequence",
      "option_name": "护盾术",
      "condition": "目标可在伤害结算前响应",
      "description": "可在伤害结算前用护盾术改变结果",
      "metadata": {{"incoming_effect": "magic_missile"}}
    }}
  ],
  "resolution_effects": [],
  "triggered_chains": []
}}
```

输出示例 3：响应动作

```json
{{
  "success": true,
  "narration": "艾尔德拉施放护盾术，法术位和反应已消耗，本次魔法飞弹被抵消",
  "direct_changes": [
    {{"path": "Aldera.resources.reaction", "old_value": "available", "new_value": "used", "operation": "MOD"}},
    {{"path": "Aldera.spells.1环法术位", "old_value": "2/4", "new_value": "1/4", "operation": "MOD"}}
  ],
  "consequence_changes": [],
  "decision_points": [],
  "resolution_effects": [
    {{"effect_type": "negate_consequence"}}
  ],
  "triggered_chains": []
}}
```
