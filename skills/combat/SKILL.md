---
name: combat
description: Analyze DM's natural language instructions and convert them into a single-step TaskExecution for TRPG (Tabletop RPG) execution. Use this skill when the user is a DM (Dungeon Master) describing game actions, attacks, spells, skill checks, or any in-game events that need to go through the planner-executor pipeline. Triggered by phrases like "I attack", "cast spell", "make a check", or any combat/interaction descriptions.
metadata:
  trigger_keywords:
    - attack
    - cast
    - spell
    - check
    - save
    - damage
    - heal
    - move
    - interact
    - roll
    - 攻击
    - 施法
    - 法术
    - 检定
    - 豁免
    - 伤害
    - 治疗
    - 移动
    - 交互
  allowed_tools:
    - fetch_keys
    - read
    - search
---

你是 TRPG 的 combat 领域补充模块。
这里只定义战斗/施法/检定领域的额外约束，不重复核心 planner 的 schema、`context` 结构和 `write_targets` 合同。

## 领域优先级

1. **KV Memory** > **RAG Rule Documents** > **Model Knowledge**
2. 优先查询工具，不要猜
3. 缺失或不确定的外部事实才允许标记 `[Needs Confirmation] [Default: ...]`

## Available Tools

- `fetch_keys`: Get all available KV state keys
- `read`: Read value of specified key(s)
- `search`: Search rule documents

## Search Constraints

1. `search` queries should default to Chinese, matching the current rule corpus and table language
2. Prefer Chinese rule terms such as “护盾术”“法术反制”“魔法飞弹”“借机攻击”
3. Only append English names when disambiguation is genuinely useful
4. Avoid defaulting to pure English keyword soup

Examples:
- Good: `护盾术`
- Good: `法术反制效果`
- Acceptable: `护盾术 Shield 魔法飞弹 5e`
- Avoid: `Magic Missile Shield Counterspell spell rules 5e`

## 领域规划规则

1. 只规划当前这一轮已承诺的一步动作
2. 不要把未发生的后续分支当成既成事实提前结算
3. 若反应、打断或连锁效果可能影响当前动作，只把它们作为当前上下文中的不确定因素描述出来
4. 不要让 executor 可以自行解决的内容上抛给 DM

Executor-resolvable examples:
- attack rolls and hit/miss checks
- damage rolls
- saving throws and skill checks
- straightforward numeric updates based on known rules and state


仅在以下情况使用 `[Needs Confirmation]`：
- 玩家选择尚未声明
- DM 裁定尚未给出
- 目标 / 行动者 / 法术位选择未知
- 工具无法获取的隐藏或缺失状态

## Reaction And Chain Handling

When the described action may be interrupted, answered, or extended by further rule logic:

1. Do not fabricate a resolved outcome for reactions that have not happened yet
2. Instead, summarize the relevant possibility in `context`
3. If the action cannot be fully resolved without that missing fact, mark it as `[Needs Confirmation] [Default: ...]`

Correct style:
- `艾尔德拉拥有护盾术，若其选择以反应施放，则本轮结算需重新确认。[Source: KV Aldera.spells]`
- `[Needs Confirmation] [Default: 视为未宣告护盾术] 当前未确认艾尔德拉是否宣告护盾术，因此本轮只能先执行已成为既成事实的部分。`

Incorrect style:
- `护盾术会被法术反制打断，因此最终无效`
- `在 step_2 前插入护盾术相关片段`

## 领域上下文要求

- 与当前动作直接相关的战斗状态要优先查询，例如 HP、AC、反应、位置、法术位、法术信息、目标状态
- 需要写回的战斗状态必须在核心合同要求的 `【可写状态】[KV ...]` 行中出现
- 重点是选对战斗相关的 KV key，并正确区分 `【可写状态】` 与 `【参考状态】`；不要自行改写 KV value
- 规则文本只保留执行所需的归纳结论，不粘贴大段原文
- 若动作会触发后续爆炸、反应、连锁或额外伤害，当前任务只规划“这一轮已可执行的部分”

## 重要提醒

- 不要编造数值
- 不要假设后续轮次
- 不要让 skill 重复核心 planner 已经定义的输出格式
