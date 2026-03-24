# TRPG Resolution Engine

一个用 JSON 驱动的 D&D 5e 判定解析引擎。

简单来说：你给它一份任务文档和当前战斗状态，它会依次完成目标选择、检定、伤害/治疗结算、效果施加、资源扣减等工作，最后更新状态并返回一份结构化的执行报告。

这个引擎的核心思路不是把固定流程硬编码，而是将常见结算拆解成可自由组合的原子操作。无论是单次攻击、范围法术，还是带条件分支的复杂技能，都能用一份 JSON 描述清楚。

## 快速开始

想看效果？直接跑内置 demo 是最快的方式。

**运行单个案例：**

```bash
python -B main.py fireball
```

**批量运行所有 demo：**

```bash
python -B main.py all
```

**查看原始结构化结果（而非人类可读摘要）：**

```bash
python -B main.py fireball --json
```

**运行完整测试：**

```bash
python -B -m unittest discover -s tests -v
```

## 架构概览

引擎分为两层：

| 层级 | 职责 | 使用场景 |
|------|------|----------|
| 引擎核心 `trpg_py.execute_task()` | 读取任务文档、校验结构、逐步执行、写回状态、生成执行报告 | 正式程序调用 |
| Demo 入口 `main.py` | 快速运行内置案例、查看输出效果 | 演示和调试 |

如果你在自己的代码中接入这套引擎，直接调用 Python API 即可。

## 最小可运行示例

```python
from trpg_py import FixedDiceRoller, execute_task

document = {
    "task_id": "simple_attack",
    "version": 1,
    "steps": [
        {
            "id": "attack",
            "type": "check",
            "kind": "attack",
            "tags": ["nat"],
            "args": {
                "dice": "1d20",
                "modifier": 5,
                "target_id": "hero_1",
                "target_ac": 15,
            },
        }
    ],
}

state = {
    "actors": {
        "hero_1": {
            "ac": 15,
            "hp": {"current": 20, "max": 20},
            "effects": [],
        }
    }
}

report = execute_task(document, state, roller=FixedDiceRoller([17]))

print(report.status)
print(report.results)
print(report.to_dict())
print(state)
```

**两点注意事项：**

1. `state` 会被**原地修改**——执行结束后，你手上的状态对象已经是结算后的结果
2. `roller` 是可注入的——测试时用 `FixedDiceRoller`，正式环境用默认随机骰子

## 理解流水线

初次接触这套 JSON 结构，最好的方式是把它想象成一条**流水线**：

```
选择目标 -> 执行检定 -> 结算伤害/治疗/效果/资源 -> 写回状态
```

任务文档的核心是 `steps` 字段。每个步骤只做一件事，前一步的输出可以作为后一步的输入。

一个典型的战斗流程长这样：

```
select.target / select.area
    -> check.attack / check.save
    -> damage.apply / heal.apply
    -> effect.add / resource.consume / state.set
```

这种设计的优点是：
- 规则语义集中，不会散落在各处
- 添加新技能或状态结构时，通常只需新增 JSON，无需改代码

## 任务文档结构

一份任务文档的顶层结构：

| 字段 | 说明 |
|------|------|
| `task_id` | 任务唯一标识 |
| `version` | 文档版本 |
| `policy` | 执行策略 |
| `context` | 任务上下文 |
| `steps` | 执行步骤列表 |

每个步骤至少包含：

| 字段 | 说明 |
|------|------|
| `id` | 步骤标识 |
| `type` | 步骤类型 |
| `kind` | 具体种类 |
| `args` | 参数 |

可选字段：

| 字段 | 说明 |
|------|------|
| `tags` | 标签（如 `nat`、`adv`） |
| `when` | 条件执行 |

### 完整示例：地精弯刀攻击

```json
{
  "task_id": "goblin_scimitar_attack",
  "version": 1,
  "context": {
    "actor_id": "goblin_1",
    "target_id": "hero_1"
  },
  "steps": [
    {
      "id": "pick_target",
      "type": "select",
      "kind": "target",
      "args": {
        "source": { "$ref": "context.target_id" }
      }
    },
    {
      "id": "attack_roll",
      "type": "check",
      "kind": "attack",
      "tags": ["nat"],
      "args": {
        "dice": "1d20",
        "modifier": { "$ref": "state.actors.goblin_1.attacks.scimitar.to_hit" },
        "target_id": { "$ref": "context.target_id" },
        "target_ac": { "$ref": "state.actors.hero_1.ac" }
      }
    },
    {
      "id": "apply_damage",
      "type": "damage",
      "kind": "apply",
      "when": {
        "$ref": "result.attack_roll.outcome",
        "in": ["success", "crit_success"]
      },
      "args": {
        "targets": { "$ref": "result.pick_target.target_ids" },
        "damage": [
          { "dice": "1d6", "bonus": 2, "damage_type": "slashing" }
        ],
        "is_critical": {
          "$ref": "result.attack_roll.outcome",
          "eq": "crit_success"
        }
      }
    }
  ]
}
```

**一句话总结**：任务文档不是脚本语言，而是一份"结算流程说明书"。

## 引用、结果与条件

### 读取数据

使用结构化 `$ref` 统一引用：

```json
{ "$ref": "context.actor_id" }      // 任务上下文
{ "$ref": "state.actors.hero_1.ac" }  // 当前状态
{ "$ref": "result.attack_roll.outcome" }  // 前序步骤结果
```

### 条件执行

`when` 控制步骤是否执行。最常见的用法是"命中才结算伤害"：

```json
{
  "when": {
    "$ref": "result.attack_roll.outcome",
    "in": ["success", "crit_success"]
  }
}
```

条件不满足时，步骤不会报错，而是被标记为 `skipped`。

## 状态组织

状态是一个嵌套字典，通过点分路径读写：

- `actors.hero_1.hp.current`
- `actors.wizard_1.resources.spell_slots.1`
- `combatants.goblin_custom_1.tracks.health.value`

引擎默认会按以下字段名查找：

- `actors.<id>.ac`
- `actors.<id>.hp.current` / `actors.<id>.hp.max`
- `actors.<id>.effects`
- `actors.<id>.saves.<ability>`
- `actors.<id>.skills.<skill>`

如果你的状态符合这种结构，很多步骤都可以写得很简洁。

## 自定义状态结构

如果状态字段名与默认布局不同，显式指定路径即可。

### 目标选择：使用 `field_map`

```json
{
  "field_map": {
    "id": "meta.id",
    "side": "team.side",
    "alive": "status.alive",
    "tags": "traits.tags",
    "position.x": "space.grid.col",
    "position.y": "space.grid.row"
  }
}
```

### 检定、伤害、效果：使用路径模板

支持以下模板参数：

| 参数 | 说明 |
|------|------|
| `target_ac_path` / `target_ac_path_template` | AC 路径 |
| `modifier_path` / `modifier_path_template` | 修正值路径 |
| `target_hp_path` / `target_hp_path_template` | 生命值路径 |
| `target_hp_max_path` / `target_hp_max_path_template` | 生命上限路径 |
| `effects_path` / `effects_path_template` | 效果列表路径 |

示例：

```json
{
  "modifier_path_template": "combatants.{target_id}.numbers.saves.dexterity",
  "target_hp_path_template": "combatants.{target_id}.tracks.health.value"
}
```

完整示例见 `examples/custom_layout_fireburst.json`。

## 支持的步骤类型

### 目标选择

| 步骤 | 说明 |
|------|------|
| `select.target` | 选择单个目标 |
| `select.area` | 范围选择（支持 `sphere`、`line`、`cone`、`target` 模板） |
| `select.filtered` | 带过滤条件的选择 |

### 检定

| 步骤 | 说明 |
|------|------|
| `check.attack` | 攻击检定 |
| `check.save` | 豁免检定 |
| `check.ability` | 能力检定 |
| `check.skill` | 技能检定 |

**标签**：`nat`（显示天然骰）、`adv`（优势）、`disadv`（劣势）

**特殊规则**：
- 攻击检定：天然 20 → `crit_success`，天然 1 → `crit_fail`
- 豁免/能力/技能检定：天然 20 和 1 不改变成败
- 优势与劣势先归并为三态：`normal`、`advantage`、`disadvantage`

### 伤害与治疗

| 步骤 | 说明 |
|------|------|
| `damage.apply` | 应用伤害（支持多段伤害、`on_save=half/none`、暴击翻倍骰子） |
| `heal.apply` | 应用治疗（支持固定值/骰子、生命上限封顶） |

### 其他操作

| 步骤 | 说明 |
|------|------|
| `resource.consume` | 消耗资源 |
| `effect.add` / `effect.remove` | 添加/移除效果 |
| `state.set` / `state.adjust` | 设置/调整状态 |

## 给 LLM 的生成建议

如果你打算让 LLM 直接生成任务 JSON，建议遵循以下约束：

1. **单一职责**：一个步骤只做一件事，用 `result.<step_id>` 串联
2. **显式随机输入**：所有骰子都明确写出，不要把优势、劣势、修正值塞进复杂公式
3. **先选目标**：单体和范围目标都先走 `select`，统一输出为 `target_ids`
4. **显式路径**：非默认状态结构时，把 `field_map` 和路径模板写清楚
5. **结构化组件**：优先使用结构化写法，而非自然语言公式

**推荐写法**：

```json
{
  "damage": [
    { "dice": "1d8", "bonus": 3, "damage_type": "slashing" }
  ]
}
```

**不推荐写法**：

```json
{ "formula": "2d20kh1+5 vs AC" }
```

前者更易校验、调试，也更不容易把规则语义写乱。

## 内置 Demo

| Demo | 说明 |
|------|------|
| `goblin_scimitar_attack` | 地精弯刀攻击 |
| `goblin_scimitar_attack_crit` | 同上，但固定骰为暴击 |
| `goblin_scimitar_attack_miss` | 同上，但固定骰为未命中 |
| `healing_word_cap` | 治疗法术（测试封顶） |
| `insufficient_spell_slot` | 法术位不足失败 |
| `fireball` | 火球术（范围法术） |
| `lightning_bolt_line` | 闪电束（线形范围） |
| `burning_hands_cone` | 燃烧之手（锥形范围） |
| `custom_layout_fireburst` | 自定义状态结构示例 |

`main.py all` 会按稳定顺序运行所有 demo 并输出汇总。

## 代码入口

| 文件 | 职责 |
|------|------|
| `trpg_py/executor.py` | 任务校验、顺序执行、条件跳过、执行报告 |
| `trpg_py/operations.py` | 核心规则语义 |
| `trpg_py/state.py` | 点分路径读写 |
| `main.py` | Demo 注册、单案例/批量运行、摘要输出 |

## 测试覆盖

运行全部测试：

```bash
python -B -m unittest discover -s tests -v
```

当前测试重点：

- 攻击检定的天然 20 / 天然 1
- 优势 / 劣势 / 抵消逻辑
- 豁免、能力、技能检定的天然骰语义
- 暴击伤害与免伤分支
- `sphere` / `line` / `cone` / `target` 范围选择
- 治疗封顶
- 资源不足失败
- `main.py` 的人类可读输出与批量运行模式
