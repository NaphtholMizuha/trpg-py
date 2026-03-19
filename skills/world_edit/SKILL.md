---
name: world_edit
description: Parse DM's direct world state manipulation instructions into a single-step TaskExecution with `task_category=world_edit`. Use this skill when the DM is directly modifying game state (not through normal gameplay mechanics), such as "set goblin HP to 0", "spawn a new monster", "heal everyone to full", "delete that NPC", or any "DM override" style commands that bypass normal dice rolling and mechanics.
metadata:
  trigger_keywords:
    - set
    - create
    - delete
    - modify
    - update
    - add
    - remove
    - spawn
    - kill
    - heal to
    - set hp
    - hp设为
    - hp改为
    - hp变为
    - to full
    - to max
    - max hp
    - 设置
    - 设为
    - 改为
    - 变为
    - 创建
    - 删除
    - 修改
    - 更新
    - 添加
    - 移除
    - 生成
    - 杀死
    - 治疗到
    - 回满
    - 满血
    - 满状态
    - 生命值
    - 生命值设为
    - 生命值改为
    - 设置生命
    - 直接
    - 立即
    - world edit
    - dm override
  allowed_tools:
    - fetch_keys
    - read
    - search
---

你是 TRPG 的 world_edit 领域补充模块。
这里只定义直接改世界状态时的领域差异，不重复核心 planner 的 schema、`context` 结构和 `write_targets` 合同。

## When to Use This Skill

Use this skill when the DM issues direct state manipulation commands that bypass normal gameplay mechanics.

Typical triggers:
- "Set goblin HP to 0" / "地精HP设为0"
- "Spawn a new orc warrior" / "生成一个新的兽人战士"
- "Delete the trap" / "删除那个陷阱"
- "Heal everyone to full HP" / "所有人回满血"
- "Add 100 gold to player's inventory" / "给玩家加100金币"
- "Modify the weather to rainy" / "把天气改成雨天"
- "DM override: the door is now unlocked" / "DM裁决：门现在开了"

Key characteristics:
- bypasses normal dice rolling
- directly sets / updates / deletes state
- administrative or DM fiat actions
- world-building and setup commands

## 领域职责

1. 识别这是直接世界编辑，而不是普通战斗结算
2. 识别目标实体、受影响字段和预期结果
3. 仍然只产出单步任务
4. 把直接变更意图、目标和必要假设放进核心合同要求的 `context`
5. 目标不清或语义歧义时才标记 `[Needs Confirmation]`

## Available Tools

Use tools only when useful:
- `fetch_keys`: inspect available state keys
- `read`: read current values for reference
- `search`: search templates or rule text when entity details matter

## 领域规则

1. `task_category` 应为 `world_edit`
2. 直接世界编辑不经过正常掷骰与战斗机制，除非 DM 明确要求
3. 不在 planner 阶段直接产出 `field_changes`
4. 不输出多步脚本、宏或附录
5. 若编辑含义不清，保持任务最小化，并用 `[Needs Confirmation]` 标记歧义

## 领域上下文要求

- 说明 DM 想直接改变什么
- 说明哪一个实体或 key 会受影响
- 必要时说明这更像 ADD / MOD / DEL 中哪一类
- 任何会被写回的当前值，都按核心合同写成 `【可写状态】[KV ...] ...`
- 缺失信息或歧义才用 `[Needs Confirmation]`

## Operation Patterns

Recognize common world edit intents:

- **ADD**: create new entities, items, effects, locations
- **MOD**: change HP, AC, status, inventory, weather, position, lock state
- **DEL**: remove entities, traps, effects, objects

These labels do not need to be emitted as a top-level schema field unless they are useful inside `context`.

## 重要提醒

- world_edit 默认不掷骰
- 不要强迫 planner 预计算过低层的 patch 细节，除非当前字段已非常明确
- 保持歧义诚实，不要编造目标
- 不要让 skill 重复核心 planner 已经定义的输出格式
