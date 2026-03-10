"""
TaskAgent - 任务Agent，规划执行步骤
"""
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from ..enums import TaskType
from ..types import TaskIntent
from ..types import RelevantPaths
from ..types import ExecutionStep, ExecutionPlan


class TaskAgent:
    """任务Agent - 根据规则和状态规划执行步骤"""
    
    def __init__(self, model: str = "gpt-4o", api_key: str | None = None, base_url: str | None = None):
        self.use_llm = api_key is not None
        
        if self.use_llm:
            kwargs = {"model": model, "temperature": 0, "api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.llm = ChatOpenAI(**kwargs)
        else:
            self.llm = None
    
    def plan(self, task: TaskIntent, state_summary: str, rules: str = "") -> ExecutionPlan:
        """根据任务、状态摘要和规则生成执行计划"""
        if not self.use_llm:
            print("   ⚠️ 未配置LLM，使用fallback")
            return self._fallback_plan(task, state_summary)
        
        # 使用RagAgent提供的规则（如果有）
        rules_content = rules if rules else "[无特定规则，使用通用D&D 5e规则]"
        
        system_prompt = """你是一个D&D 5e战斗执行规划器。

根据任务描述、战场状态摘要和查询到的D&D 5e规则，生成执行步骤。

输出必须是JSON格式：
{
    "steps": [
        {
            "step_id": "step_1",
            "description": "步骤描述",
            "expression": "逻辑表达式，使用Roll('XdY')格式掷骰",
            "condition": "执行条件（总是/命中时/等）",
            "state_changes": [{"path": "...", "operation": "subtract", "value_expr": "..."}]
        }
    ]
}

重要规则：
1. 掷骰必须使用 Roll('XdY') 格式，如 Roll('1d20'), Roll('1d8')
2. 引用状态使用完整路径，如 entity.players.player_01.attributes.modifiers.strength
3. 步骤结果引用使用 step_1_result, step_2_result 等
4. 状态变更的 value_expr 可以是数字、step_X_result 或字符串（用单引号包裹）

优化原则（重要）：
- D&D 5e 大成功/大失败规则（必须处理）：
  * 自然20（骰面显示20）：自动命中 + 暴击（伤害骰翻倍，如Roll('2d8')）
  * 自然1（骰面显示1）：自动未命中（无论加值多高）
- 表达式支持完整 Python 语法（if/elif/else、变量赋值）：
  * 可以用多行语句，最后一行是返回值
  * if 语句惰性求值（只执行命中分支的 Roll）
- 物品与生物的处理区别（重要）：
  * 生物：进行豁免检定（saving throw）、受暴击规则影响
  * 物品：通常不做豁免检定（某些需要DM判定），直接应用效果（如被点燃、被摧毁）
  * 如果目标是[物品]，不要让它做豁免检定，直接执行效果

必须根据上面提供的D&D 5e规则来生成步骤，不要依赖模型记忆。

只输出JSON，不要其他解释。"""

        prompt = f"""任务：{task.description}
类型：{task.task_type.value}
行动者：{task.actor}
目标：{task.target}
动作：{task.action}

战场状态摘要：
{state_summary}

查询到的D&D 5e规则：
{rules_content}

请根据以上规则生成执行计划。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            content = response.content.strip()
            
            # 清理 markdown 代码块
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            print(f"   🤖 LLM计划:\n{content[:400]}...")
            
            data = json.loads(content)
            
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
                required_rules=[]
            )
            
        except Exception as e:
            print(f"   ⚠️ LLM计划生成失败: {e}，使用fallback")
            return self._fallback_plan(task, state_summary)
    
    def _fallback_plan(self, task: TaskIntent, state_summary: str) -> ExecutionPlan:
        """生成回退执行计划"""
        steps = []
        
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
            # 伤害：武器骰 + 调整值
            if "弯刀" in task.action:
                damage_expr = "Roll('1d6') + 2"
            else:
                damage_expr = "Roll('1d8') + 3"
            
            # 步骤1：攻击检定 + 命中判定（合并）
            steps.append(ExecutionStep(
                step_id="step_1",
                description="攻击检定并判定命中",
                expression=f"Roll('1d20') + {actor_path}.attributes.modifiers.strength + 3 >= {target_path}.ac",
                condition="总是",
                state_changes=[]
            ))
            # 步骤2：计算伤害（仅命中时执行）
            steps.append(ExecutionStep(
                step_id="step_2",
                description="计算伤害",
                expression=damage_expr,
                condition="命中时",
                state_changes=[{
                    "path": target_hp_path,
                    "operation": "subtract",
                    "value_expr": "step_2_result"
                }]
            ))
            
        elif task.task_type == TaskType.SPELL:
            if "圣火术" in task.action:
                if task.target == "火药桶":
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
        
        return ExecutionPlan(
            task_id=task.task_id,
            steps=steps,
            required_rules=[]
        )
