# TRPG Skills 系统

Anthropic风格的Skill系统，用于TRPG PlannerAgent的意图识别和动态提示词加载。

## 设计理念

借鉴Anthropic的Skills系统：
- 使用YAML frontmatter定义元数据
- Markdown格式编写指令
- 关键词触发机制
- 动态加载和切换

## 文件结构

```
skills/
├── combat/
│   └── SKILL.md          # 标准游戏流程Skill (战斗、施法、检定等)
├── world_edit/
│   └── SKILL.md          # 世界编辑/DM覆盖Skill
└── README.md             # 本文档
```

## Skill格式

```yaml
---
name: skill-name-in-kebab-case
description: 描述skill的功能和使用场景，用于意图识别
metadata:
  trigger_keywords:
    - keyword1
    - keyword2
    - 关键词3
---

## 指令内容

这里是详细的操作指南，支持Markdown格式...
```

## 已实现的Skills

### combat

**用途**: 处理标准游戏流程（攻击、施法、检定等）

**触发关键词**:
- attack, cast, spell, check, save, damage, heal, move, interact, roll
- 攻击, 施法, 法术, 检定, 豁免, 伤害, 治疗, 移动, 交互

**特点**:
- 使用ReAct模式
- 支持工具调用（fetch_keys, read, search）
- 生成自然语言任务描述
- 检测连锁反应和可能的反应

### world_edit

**用途**: 处理DM直接世界状态修改（set, create, delete等）

**触发关键词**:
- set, create, delete, modify, update, add, remove, spawn, kill
- 设置, 创建, 删除, 修改, 更新, 添加, 移除, 生成, 杀死
- to full, to max, 回满, 满血

**特点**:
- 跳过骰子检定
- 直接生成字段级变更
- 标注dm_override标志
- 输出JSON格式

## 意图识别流程

```
用户输入
    ↓
关键词匹配（world_edit优先）
    ↓
选择对应Skill
    ↓
加载Skill内容作为系统提示词
    ↓
执行对应的处理流程
```

## 使用方法

### 在PlannerAgent中使用

```python
from src.agents import PlannerAgent
from src.tools import create_tools

tools = create_tools()
planner = PlannerAgent(
    model="gpt-4o",
    api_key="your-api-key",
    tools=tools,
    use_skills=True  # 启用skills系统
)

# 标准指令
result1 = planner.plan("艾尔德拉攻击地精")
# 使用combat skill

# 世界编辑指令
result2 = planner.plan("set goblin HP to 0")
# 使用world_edit skill
```

### 直接使用意图识别

```python
from src.skills import detect_intent

intent_type, skill = detect_intent("生成一个新怪物")
print(intent_type)  # "world_edit"
print(skill.name)   # "world_edit"
```

## 添加新Skill

1. 创建目录: `mkdir skills/my_skill`
2. 创建文件: `skills/my_skill/SKILL.md`
3. 编写内容（参考现有skill格式）
4. 重新加载: `get_registry()._load_all_skills()`

### 示例：添加历史查询Skill

```yaml
---
name: dice-history
description: 查询历史骰子记录和统计信息
metadata:
  trigger_keywords:
    - history
    - 历史
    - 统计
    - 之前投了多少
---

## 历史查询指令

当用户想要查看历史骰子记录时：
1. 查询KV存储中的历史记录
2. 汇总统计信息
3. 输出格式化的历史报告
```

## 集成架构

```
User Input
    ↓
SkillRegistry.detect_intent()
    ↓
PlannerAgent.plan()
    ├── Standard Flow (combat)
    │   ├── ReAct loop with tools
    │   ├── Generate natural language task
    │   └── Return PlannedTask
    │
    └── World Edit Flow (world_edit)
        ├── Parse direct modification
        ├── Generate JSON field changes
        └── Return PlannedTask (with dm_override)
```

## 与原始Prompt系统的关系

- **原prompts/**: 作为默认/备用系统
- **skills/**: 动态覆盖，优先级更高
- 可以通过 `use_skills=False` 禁用skill系统

## 未来扩展

可能的额外skills:
- `combat-tracker`: 复杂战斗追踪
- `npc-dialogue`: NPC对话生成
- `loot-generator`: 战利品生成
- `scene-description`: 场景描述生成
- `rule-lookup`: 规则速查
