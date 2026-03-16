请执行以下任务:

任务ID: {task_id}
任务描述: {description}
行动者: {actor}
目标: {target}
DM批注: {dm_notes}

任务详情:
{context}

工作流程（严格执行）：

**STEP 1: 读取任务信息**
- 从task.context获取相关状态信息
- 如有DM批注，请优先考虑批注中的指示

**STEP 2: 【关键】检查 Planner 预判的反应列表**
```
IF task.potential_reactions 不为空:
    FOR 每个 reaction IN task.potential_reactions:
        使用 read 工具查询当前状态，验证 reaction.condition 是否达成
        IF 条件达成:
            进入 **反应检查模式 (REACTION MODE)**
        ENDIF
    ENDFOR
ELSE:
    进入 **正常执行模式 (NORMAL MODE)**
ENDIF
```

**STEP 3: 使用 evaluate 执行掷骰和计算**

**STEP 4: 根据模式执行不同的变更策略**

▶️ **正常执行模式 (NORMAL MODE)** - 无反应或条件不达成：
- `field_changes` 包含所有变更（施法者消耗 + 目标伤害）
- `pending_changes` = 空数组 []
- `triggered_chains` = 空数组 []
- 调用 write_fields 写入所有变更

▶️ **反应检查模式 (REACTION MODE)** - 反应条件已达成：
- `field_changes` **只包含施法者资源消耗**（如法术位，立即应用）
- `pending_changes` **包含目标伤害**（等待反应确认，暂不应用）
- `triggered_chains` **必须包含 reaction_check**
- 调用 write_fields **只写入施法者消耗**（目标伤害不写入！）

**关键区分**：
- `field_changes` = 立即应用的变更（施法者法术位、消耗品等）
- `pending_changes` = 等待反应确认的变更（目标HP、状态等）

**STEP 5: 检测简单连锁条件（HP归零、爆炸、坍塌）**
**STEP 6: 输出JSON格式的执行结果**

⚠️ **绝对规则（必须遵守）**：
1. 执行前**必须**检查 `task.potential_reactions`
2. 如果 `potential_reactions` 不为空且条件达成，**绝对不能**将目标伤害放入 `field_changes`
3. 反应检查模式下，`triggered_chains` **必须**包含 `{{"type": "reaction_check", ...}}
4. new_value必须是完整的自然语言段落
5. 输出必须是JSON格式，包含success, narration, field_changes, pending_changes, triggered_chains字段

**护盾术特殊效果**：护盾术可以完全免疫魔法飞弹伤害（5e规则）

**连锁判断**: 根据执行结果判断是否需要触发连锁
  * 检查状态变化是否符合连锁条件
  * 考虑DM批注：如果DM批注明确说明不需要某连锁（如"不需要死亡豁免"），则不触发
  * 如果无连锁，triggered_chains设为空数组 []

输出JSON格式示例（严格区分两种模式）：

═══════════════════════════════════════════════════════════════════
▶️ 模式A：正常执行模式（无反应或反应条件不达成）
═══════════════════════════════════════════════════════════════════

**条件**: task.potential_reactions 为空，或所有反应条件验证失败

**输出示例**:
```json
{{
  "success": true,
  "narration": "攻击命中，造成10点伤害，哥布林HP从10降至0",
  "field_changes": [
    {{"path": "Goblin.combat.HP", "old_value": "10/10", "new_value": "0/10", "operation": "MOD"}}
  ],
  "pending_changes": [],
  "triggered_chains": [
    {{"type": "death", "description": "哥布林HP降至0，触发死亡连锁", "source_key": "Goblin.combat"}}
  ]
}}
```

═══════════════════════════════════════════════════════════════════
▶️ 模式B：反应检查模式（反应条件已达成 - 关键！）
═══════════════════════════════════════════════════════════════════

**条件**: task.potential_reactions 不为空，且验证后反应条件已达成

**规则**：
- `field_changes` = **只有施法者资源消耗**（法术位等）
- `pending_changes` = **只有目标伤害/效果**（等待反应确认）
- `triggered_chains` = **必须包含 reaction_check**
- 调用 write_fields 时**只写入 field_changes**（施法者消耗）

**场景B1：魔法飞弹攻击有护盾术的目标**
```json
{{
  "success": true,
  "narration": "马利克施放魔法飞弹（1环），3发飞镖射向艾尔德拉。检测到艾尔德拉反应可用且准备有护盾术，护盾术可完全免疫魔法飞弹。马利克的1环法术位已从4/4消耗至3/4。伤害结算等待反应确认...",
  "field_changes": [
    {{"path": "Malik.spells.1环法术位", "old_value": "4/4", "new_value": "3/4", "operation": "MOD"}}
  ],
  "pending_changes": [
    {{"path": "Aldera.combat.HP", "old_value": "44/44", "new_value": "37/44", "operation": "MOD"}}
  ],
  "triggered_chains": [
    {{"type": "reaction_check", "description": "艾尔德拉可用护盾术完全抵挡魔法飞弹伤害", "actor": "艾尔德拉", "spell": "护盾术"}}
  ]
}}
```
⚠️ **注意**：`field_changes` 没有艾尔德拉的HP变更！伤害只在 `pending_changes` 中！

**场景B2：普通攻击，目标有护盾术可用**
```json
{{
  "success": true,
  "narration": "哥布林短剑攻击命中艾尔德拉（AC 18 vs 攻击骰 22），计算得6点伤害。检测到艾尔德拉反应可用，可能使用护盾术提升AC至23使攻击未命中。伤害结算等待反应确认...",
  "field_changes": [],
  "pending_changes": [
    {{"path": "Aldera.combat.HP", "old_value": "44/44", "new_value": "38/44", "operation": "MOD"}}
  ],
  "triggered_chains": [
    {{"type": "reaction_check", "description": "艾尔德拉可用护盾术提升AC，可能使攻击未命中", "actor": "艾尔德拉", "spell": "护盾术"}}
  ]
}}
```
⚠️ **注意**：`field_changes` 为空（此攻击无施法者消耗），`pending_changes` 包含伤害！

═══════════════════════════════════════════════════════════════════
**检查清单（输出前必须确认）**
═══════════════════════════════════════════════════════════════════

□ `potential_reactions` 是否为空？
   - 是 → `field_changes` 包含所有变更，`pending_changes` = []
   - 否 → 继续检查

□ 反应条件是否已达成？
   - 否 → `field_changes` 包含所有变更，`pending_changes` = []
   - 是 → 进入反应检查模式

□ 反应检查模式下：
   - □ `field_changes` 只包含施法者资源消耗（如法术位）
   - □ `pending_changes` 包含目标伤害/效果
   - □ `triggered_chains` 包含 `{{"type": "reaction_check", ...}}`
   - □ write_fields 只写入 `field_changes` 中的变更
