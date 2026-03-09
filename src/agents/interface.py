"""
InterfaceAgent - 交互Agent，理解DM输入生成任务意图
"""
import json
import uuid
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from ..enums import TaskType
from ..types import TaskIntent


class InterfaceAgent:
    """交互Agent - 理解DM输入，生成任务意图"""
    
    def __init__(self, model: str = "gpt-4o", api_key: str | None = None, base_url: str | None = None):
        self.use_llm = api_key is not None
        if self.use_llm:
            kwargs = {"model": model, "temperature": 0, "api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.llm = ChatOpenAI(**kwargs)
        else:
            self.llm = None
    
    def parse(self, user_input: str) -> TaskIntent:
        """解析用户输入为任务意图"""
        if not self.use_llm:
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
            content = response.content.strip()
            
            # 清理 markdown 代码块标记
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
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
            print(f"   ⚠️ LLM意图识别失败: {e}，使用fallback")
            return self._fallback_parse(user_input)
    
    def _fallback_parse(self, user_input: str) -> TaskIntent:
        """简单回退解析 - 基于句法分析"""
        has_aildra = "艾尔德拉" in user_input
        has_goblin = "地精" in user_input or "哥布林" in user_input
        has_barrel = "火药桶" in user_input or "桶" in user_input
        
        first_entity_pos = float('inf')
        actor = "未知"
        
        if has_aildra:
            pos = user_input.find("艾尔德拉")
            if pos < first_entity_pos:
                first_entity_pos = pos
                actor = "艾尔德拉"
        
        if has_goblin:
            pos = user_input.find("地精掠夺者")
            if pos == -1:
                pos = user_input.find("地精")
            if pos == -1:
                pos = user_input.find("哥布林")
            if pos < first_entity_pos:
                first_entity_pos = pos
                actor = "地精掠夺者"
        
        target = None
        if has_aildra and actor != "艾尔德拉":
            target = "艾尔德拉"
        elif has_goblin and actor != "地精掠夺者":
            target = "地精掠夺者"
        elif has_barrel:
            target = "火药桶"
        
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
