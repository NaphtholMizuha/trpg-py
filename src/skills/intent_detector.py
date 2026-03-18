"""
LLM-based 意图识别器

使用轻量级LLM调用来进行意图分类，出错时fallback到关键词匹配
"""
from typing import Any
import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from . import get_registry, Skill


class IntentDetector:
    """意图识别器 - LLM-based，出错时fallback到关键词匹配"""

    def __init__(
        self,
        model: str = "gpt-4o-mini",  # 使用轻量级模型
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0,
    ):
        """
        初始化意图识别器

        Args:
            model: 使用的模型名称，默认gpt-4o-mini（轻量且便宜）
            api_key: API密钥，默认从环境变量读取
            base_url: 自定义base_url
            temperature: 温度，意图识别用0最稳定
        """
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL")
        self.temperature = temperature
        self._llm: ChatOpenAI | None = None
        self._registry = get_registry()

    def _get_llm(self) -> ChatOpenAI:
        """懒加载LLM实例"""
        if self._llm is None:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "temperature": self.temperature,
            }
            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._llm = ChatOpenAI(**kwargs)
        return self._llm

    def detect(self, user_input: str) -> tuple[str, Skill | None]:
        """
        检测用户意图

        先尝试LLM-based识别，出错时fallback到关键词匹配

        Returns:
            (intent_type, skill)
            intent_type: "standard" | "world_edit"
        """
        try:
            return self._detect_with_llm(user_input)
        except Exception as e:
            # LLM识别失败，fallback到关键词匹配
            print(f"[IntentDetector] LLM识别失败，使用关键词fallback: {e}")
            return self._detect_with_keywords(user_input)

    def _detect_with_llm(self, user_input: str) -> tuple[str, Skill | None]:
        """使用LLM进行意图识别"""
        # 构建可用skills的描述
        skills_desc = []
        for name, skill in self._registry._skills.items():
            skills_desc.append(f"- {name}: {skill.description}")

        prompt = f"""分析以下TRPG DM指令的意图类型，选择最合适的skill。

可用Skills:
{chr(10).join(skills_desc)}

DM指令: "{user_input}"

规则:
1. world_edit: DM直接修改游戏世界状态，绕过正常游戏规则（如"set HP to 0", "生成怪物", "直接杀死"）
2. combat: 标准游戏流程，需要掷骰和规则判定（如"攻击", "施法", "检定"）

只输出skill名称（combat 或 world_edit），不要解释。"""

        messages = [
            SystemMessage(content="你是一个TRPG意图分类器。只输出skill名称，不要任何解释。"),
            HumanMessage(content=prompt)
        ]

        response = self._get_llm().invoke(messages)
        content = response.content
        if isinstance(content, list):
            content = " ".join(str(item) for item in content)
        skill_name = content.strip().lower()

        # 清理可能的额外字符
        skill_name = skill_name.replace("`", "").replace("'", "").replace('"', "").strip()

        # 映射可能的变体
        name_mapping = {
            "combat": "combat",
            "world_edit": "world_edit",
            "trpg-world-edit": "world_edit",
            "world edit": "world_edit",
        }

        normalized_name = name_mapping.get(skill_name, skill_name)

        if normalized_name == "world_edit":
            return "world_edit", self._registry.get_world_edit_skill()
        elif normalized_name == "combat":
            return "standard", self._registry.get_combat_skill()
        else:
            # LLM返回了未知名称，fallback
            raise ValueError(f"LLM返回未知skill名称: {skill_name}")

    def _detect_with_keywords(self, user_input: str) -> tuple[str, Skill | None]:
        """关键词匹配fallback"""
        user_lower = user_input.lower()

        # world_edit优先
        world_edit = self._registry.get_world_edit_skill()
        if world_edit:
            for keyword in world_edit.trigger_keywords:
                if keyword.lower() in user_lower:
                    return "world_edit", world_edit

        # 然后combat
        combat = self._registry.get_combat_skill()
        if combat:
            for keyword in combat.trigger_keywords:
                if keyword.lower() in user_lower:
                    return "standard", combat

        # 默认combat
        return "standard", combat


# 全局意图识别器实例（懒加载）
_intent_detector: IntentDetector | None = None


def get_intent_detector() -> IntentDetector:
    """获取全局意图识别器实例"""
    global _intent_detector
    if _intent_detector is None:
        _intent_detector = IntentDetector()
    return _intent_detector


def detect_intent(user_input: str) -> tuple[str, Skill | None]:
    """
    检测用户意图（LLM-based，出错时fallback）

    这是主要的意图识别入口函数
    """
    return get_intent_detector().detect(user_input)
