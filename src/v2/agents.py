"""
V2 Agent 实现
"""
import json
import uuid
from typing import Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from .types import (
    TaskIntent, TaskType, RelevantPaths, ExecutionPlan, 
    ExecutionStep, LogicResult, StateChange, ChainTrigger
)


class InterfaceAgent:
    """交互Agent - 理解DM输入，生成任务意图"""
    
    def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
        self.use_llm = api_key is not None
        if self.use_llm:
            kwargs = {"model": model, "temperature": 0, "api_key": api_key}
            self.llm = ChatOpenAI(**kwargs)
        else:
            self.llm = None
        
    def parse(self, user_input: str) -> TaskIntent:
        """解析用户输入为任务意图"""
        
        if not self.use_llm:
            # 无LLM时使用回退解析
            return self._fallback_parse(user_input)
        
        system_prompt = """你是一个D&D 5e战斗意图解析器。

你的任务是将自然语言描述解析为结构化的任务意图。

任务类型定义：
- attack: 物理攻击（使用武器）
- spell: 施放法术
- interact: 环境互动（使用物品、点燃等）
- move: 移动

输出必须是JSON格式：
{
    "task_type": "attack|spell|interact|move",
    "actor": "行动者名称（如'艾尔德拉'）",
    "target": "目标名称（如'哥布林'）",
    "action": "具体动作（如'用长剑攻击'、'施放圣火术'）",
    "context": {
        "weapon": "武器名称（如果是攻击）",
        "spell": "法术名称（如果是施法）",
        "interaction": "互动类型（如果是互动）"
    }
}

只输出JSON，不要其他解释。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"解析以下描述：\n{user_input}")
        ]
        
        try:
            response = self.llm.invoke(messages)
            data = json.loads(response.content)
            return TaskIntent(
                task_id=f"task_{uuid.uuid4().hex[:8]}",
                description=user_input,
                task_type=TaskType(data["task_type"]),
                actor=data["actor"],
                target=data.get("target"),
                action=data["action"],
                context=data.get("context", {})
            )
        except Exception as e:
            # 回退：简单解析
            return self._fallback_parse(user_input)
    
    def _fallback_parse(self, user_input: str) -> TaskIntent:
        """简单回退解析 - 基于句法分析"""
        # 中文句法：通常 "[行动者] [动作] [目标]"
        # 例："艾尔德拉用长剑攻击地精掠夺者"
        # 例："地精掠夺者用弯刀攻击艾尔德拉"
        
        # 识别句中实体
        has_aildra = "艾尔德拉" in user_input
        has_goblin = "地精" in user_input or "哥布林" in user_input
        has_barrel = "火药桶" in user_input or "桶" in user_input
        
        # 简单启发式：第一个出现的实体通常是行动者
        first_entity_pos = float('inf')
        actor = "未知"
        
        if has_aildra:
            pos = user_input.find("艾尔德拉")
            if pos < first_entity_pos:
                first_entity_pos = pos
                actor = "艾尔德拉"
        
        if has_goblin:
            # 找"地精"或"哥布林"或"地精掠夺者"
            pos = user_input.find("地精掠夺者")
            if pos == -1:
                pos = user_input.find("地精")
            if pos == -1:
                pos = user_input.find("哥布林")
            if pos < first_entity_pos:
                first_entity_pos = pos
                actor = "地精掠夺者"
        
        # 识别目标（非行动者的实体）
        target = None
        if has_aildra and actor != "艾尔德拉":
            target = "艾尔德拉"
        elif has_goblin and actor != "地精掠夺者":
            target = "地精掠夺者"
        elif has_barrel:
            target = "火药桶"
        
        # 识别任务类型和动作
        if "攻击" in user_input or "砍" in user_input:
            task_type = TaskType.ATTACK
            if "弯刀" in user_input:
                action = "用弯刀攻击"
            elif "长剑" in user_input:
                action = "用长剑攻击"
            else:
                action = "攻击"
        elif "圣火术" in user_input:
            task_type = TaskType.SPELL
            action = "施放圣火术"
        elif "点燃" in user_input:
            task_type = TaskType.INTERACT
            action = "点燃"
        else:
            task_type = TaskType.INTERACT
            action = user_input
        
        return TaskIntent(
            task_id=f"task_{uuid.uuid4().hex[:8]}",
            description=user_input,
            task_type=task_type,
            actor=actor,
            target=target,
            action=action,
            context={}
        )


class PathFinder:
    """路径检索Agent - 根据任务检索相关状态路径"""
    
    # 实体名称到路径的映射
    ENTITY_MAP = {
        "艾尔德拉": "entity.players.player_01",
        "艾尔德拉·银誓": "entity.players.player_01",
        "地精": "entity.enemies.goblin_01",
        "哥布林": "entity.enemies.goblin_01", 
        "地精掠夺者": "entity.enemies.goblin_01",
        "火药桶": "entity.objects.explosive_barrel",
    }
    
    # 任务类型到相关字段的映射
    TASK_PATHS = {
        TaskType.ATTACK: {
            "actor": [
                "attributes.strength",
                "attributes.modifiers.strength",
                "equipment.weapons.main_hand.damage",
                "equipment.weapons.main_hand.damage_type",
                "combat.proficiency_bonus",
            ],
            "target": [
                "ac",
                "current_hp",
            ]
        },
        TaskType.SPELL: {
            "actor": [
                "attributes.charisma",
                "attributes.modifiers.charisma",
                "combat.spell_dc",
                "spell_slots",
            ],
            "target": [
                "current_hp",
                "attributes",
            ]
        },
        TaskType.INTERACT: {
            "actor": [],
            "target": [
                "state",
                "damage",
                "interact_options",
            ]
        }
    }
    
    def find_paths(self, task: TaskIntent) -> RelevantPaths:
        """根据任务找到相关路径"""
        
        primary_paths = {}
        related_paths = {}
        
        # 解析行动者路径
        actor_base = self.ENTITY_MAP.get(task.actor)
        if actor_base:
            task_paths = self.TASK_PATHS.get(task.task_type, {})
            for field in task_paths.get("actor", []):
                path = f"{actor_base}.{field}"
                path_type = self._infer_type(field)
                primary_paths[path] = path_type
        
        # 解析目标路径
        target_base = self.ENTITY_MAP.get(task.target) if task.target else None
        if target_base:
            task_paths = self.TASK_PATHS.get(task.task_type, {})
            for field in task_paths.get("target", []):
                path = f"{target_base}.{field}"
                path_type = self._infer_type(field)
                primary_paths[path] = path_type
            
            # 对于火药桶，添加 state 路径
            if "explosive_barrel" in target_base:
                primary_paths[f"{target_base}.state"] = "str"
        
        # 添加环境相关路径
        related_paths["metadata.lighting"] = "str"
        related_paths["metadata.combat_rules.cover"] = "str"
        
        return RelevantPaths(
            primary_paths=primary_paths,
            related_paths=related_paths
        )
    
    def _infer_type(self, field: str) -> str:
        """推断字段类型"""
        if field in ["strength", "dexterity", "constitution", "intelligence", 
                     "wisdom", "charisma", "current_hp", "ac", "spell_dc",
                     "proficiency_bonus"]:
            return "int"
        elif "damage" in field or "modifier" in field:
            return "int"
        elif field in ["damage", "damage_type", "state"]:
            return "str"
        else:
            return "any"


class TaskAgent:
    """任务Agent - 规划执行步骤"""
    
    def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
        self.use_llm = api_key is not None
        if self.use_llm:
            kwargs = {"model": model, "temperature": 0, "api_key": api_key}
            self.llm = ChatOpenAI(**kwargs)
        else:
            self.llm = None
    
    def plan(self, task: TaskIntent, paths: RelevantPaths) -> ExecutionPlan:
        """根据任务和可用路径生成执行计划"""
        
        if not self.use_llm:
            # 无LLM时使用回退计划
            return self._fallback_plan(task, paths)
        
        # 构建路径描述
        path_desc = "\n".join([f"- {p}: {t}" for p, t in paths.primary_paths.items()])
        
        system_prompt = f"""你是一个D&D 5e战斗执行规划器。

根据任务和可用的状态路径，生成详细的执行步骤。
可用路径：
{path_desc}

输出必须是JSON格式：
{{
    "steps": [
        {{
            "step_id": "step_1",
            "description": "步骤描述",
            "expression": "逻辑表达式（如 Roll('1d20') + entity.players.player_01.attributes.modifiers.strength）",
            "condition": "执行条件（如'总是'、'命中时'）",
            "state_changes": [{{"path": "...", "operation": "subtract", "value_expr": "..."}}]
        }}
    ],
    "required_rules": ["需要查询的规则名称"]
}}

D&D 5e攻击流程：
1. 攻击检定：d20 + 力量调整值 + 熟练加值（如果熟练）vs 目标AC
2. 伤害判定：武器伤害骰 + 力量调整值
3. 状态更新：目标HP减少

只输出JSON，不要其他解释。"""

        prompt = f"""任务：{task.description}
类型：{task.task_type.value}
行动者：{task.actor}
目标：{task.target}
动作：{task.action}

生成执行计划。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            data = json.loads(response.content)
            
            steps = []
            for i, s in enumerate(data.get("steps", [])):
                steps.append(ExecutionStep(
                    step_id=s.get("step_id", f"step_{i+1}"),
                    description=s["description"],
                    expression=s.get("expression"),
                    condition=s.get("condition"),
                    state_changes=s.get("state_changes", [])
                ))
            
            return ExecutionPlan(
                task_id=task.task_id,
                steps=steps,
                required_rules=data.get("required_rules", [])
            )
        except Exception as e:
            # 回退到硬编码计划
            return self._fallback_plan(task, paths)
    
    def _fallback_plan(self, task: TaskIntent, paths: RelevantPaths) -> ExecutionPlan:
        """生成回退执行计划"""
        steps = []
        
        # 根据行动者确定属性路径
        if task.actor == "艾尔德拉":
            actor_path = "entity.players.player_01"
            target_path = "entity.enemies.goblin_01"
            target_hp_path = "entity.enemies.goblin_01.current_hp"
        elif task.actor == "地精掠夺者":
            actor_path = "entity.enemies.goblin_01"
            target_path = "entity.players.player_01"
            target_hp_path = "entity.players.player_01.combat.current_hp"
        else:
            actor_path = "entity.players.player_01"
            target_path = "entity.enemies.goblin_01"
            target_hp_path = "entity.enemies.goblin_01.current_hp"
        
        if task.task_type == TaskType.ATTACK:
            # 确定伤害骰
            if "弯刀" in task.action:
                damage_dice = "1d6+2"
            else:  # 长剑
                damage_dice = "1d8+3"
            
            # 攻击流程
            steps.append(ExecutionStep(
                step_id="step_1",
                description="攻击检定",
                expression=f"Roll('1d20') + {actor_path}.attributes.modifiers.strength + 3",  # +3 熟练
                condition="总是",
                state_changes=[]
            ))
            steps.append(ExecutionStep(
                step_id="step_2",
                description="判定命中",
                expression=f"step_1_result >= {target_path}.ac",
                condition="总是",
                state_changes=[]
            ))
            steps.append(ExecutionStep(
                step_id="step_3",
                description="计算伤害",
                expression=f"Roll('{damage_dice}')",
                condition="命中时",
                state_changes=[{
                    "path": target_hp_path,
                    "operation": "subtract",
                    "value_expr": "step_3_result"
                }]
            ))
            
        elif task.task_type == TaskType.SPELL:
            if "圣火术" in task.action:
                if task.target == "火药桶":
                    # 点燃火药桶
                    steps.append(ExecutionStep(
                        step_id="step_1",
                        description="圣火术点燃火药桶",
                        expression="None",
                        condition="总是",
                        state_changes=[{
                            "path": "entity.objects.explosive_barrel.state",
                            "operation": "set",
                            "value_expr": "'lit'"
                        }]
                    ))
                else:
                    # 攻击地精
                    steps.append(ExecutionStep(
                        step_id="step_1",
                        description="圣火术伤害",
                        expression="Roll('2d8')",
                        condition="总是",
                        state_changes=[{
                            "path": target_hp_path,
                            "operation": "subtract",
                            "value_expr": "step_1_result"
                        }]
                    ))
            
        elif task.task_type == TaskType.INTERACT:
            if "点燃" in task.action and "火药桶" in str(task.target):
                steps.append(ExecutionStep(
                    step_id="step_1",
                    description="点燃火药桶",
                    expression="None",
                    condition="总是",
                    state_changes=[{
                        "path": "entity.objects.explosive_barrel.state",
                        "operation": "set",
                        "value_expr": "'lit'"
                    }]
                ))
                steps.append(ExecutionStep(
                    step_id="step_2",
                    description="延迟爆炸（将在本回合结束时触发）",
                    expression="None",
                    condition="总是",
                    state_changes=[]
                ))
        
        return ExecutionPlan(
            task_id=task.task_id,
            steps=steps,
            required_rules=[]
        )


class ChainAgent:
    """连锁Agent - 检测状态变更触发的连锁反应"""
    
    def check_chains(self, changes: list[StateChange], world_state: dict) -> list[ChainTrigger]:
        """检查是否有连锁反应"""
        triggers = []
        
        for change in changes:
            # 检查HP归零 - 死亡连锁
            if "current_hp" in change.path and change.new_value <= 0:
                # 提取实体ID
                path_parts = change.path.split(".")
                if len(path_parts) >= 3:
                    entity_type = path_parts[1]  # enemies
                    entity_id = path_parts[2]    # goblin_01
                    
                    entity_data = world_state.get("entity", {}).get(entity_type, {}).get(entity_id, {})
                    entity_name = entity_data.get("name", entity_id)
                    
                    triggers.append(ChainTrigger(
                        condition=f"{entity_name} HP ≤ 0",
                        effect=f"{entity_name} 死亡，触发死亡连锁（掉落物品、经验结算）",
                        priority=1
                    ))
            
            # 检查火药桶点燃
            if "explosive_barrel.state" in change.path and change.new_value == "lit":
                triggers.append(ChainTrigger(
                    condition="火药桶被点燃",
                    effect="6秒后爆炸，范围内所有生物受到 4d6 火焰 + 2d6 钝击伤害（DC12敏捷豁免减半）",
                    priority=2
                ))
        
        return triggers
