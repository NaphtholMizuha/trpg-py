"""
PlannerAgent - 规划Agent

合并意图识别 + RAG检索 + 任务生成
使用ReAct模式，通过tools决定如何执行
"""
import uuid

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import BaseTool

from ..config import PLANNER_SYSTEM_PROMPT
from ..types import PlannedTask
from ..utils.logging import get_logger
from .base import BaseAgent

logger = get_logger(__name__)


class PlannerAgent(BaseAgent):
    """
    PlannerAgent - 规划Agent

    职责:
    1. 分析玩家输入的自然语言指令
    2. 使用fetch_keys查看所有可用的KV记忆key
    3. 使用read工具查询感兴趣的key的value
    4. 使用search工具(RAG)查询D&D规则(英文)
    5. 生成自然语言任务描述，放入任务队列

    优先级策略: KV记忆 > RAG获取的内容 > 模型自身知识
    """

    SYSTEM_PROMPT = PLANNER_SYSTEM_PROMPT

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
        tools: list[BaseTool] | None = None
    ):
        super().__init__(model, api_key, base_url, tools, max_iterations=10)

    def get_system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def plan(self, user_input: str) -> PlannedTask:
        """
        将用户输入转换为PlannedTask（自然语言版本）

        使用ReAct模式:
        1. 调用LLM生成tool calls
        2. 执行tools获取信息
        3. LLM输出自然语言任务描述
        """
        logger.info("PlannerAgent 分析指令", user_input=user_input)

        # 构建对话历史
        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=f"""DM指令: {user_input}

请分析并生成自然语言任务描述。

工作流程：
1. 使用工具查询需要的信息（fetch_keys/read/search）
2. 整合信息后，输出自然语言格式的任务描述

请开始分析。""")
        ]

        # 使用基类的 ReAct 循环
        final_message = self._react_loop(
            messages,
            force_output_prompt="请直接输出自然语言任务描述，不要继续调用工具。"
        )

        content_str = ""
        if isinstance(final_message.content, str):
            content_str = final_message.content
        elif isinstance(final_message.content, list):
            content_str = "\n".join(str(item) for item in final_message.content)

        logger.info("LLM 输出", content=content_str[:200] if content_str else "None")
        return self._parse_planned_task_natural(content_str, user_input)

    def _parse_planned_task_natural(self, content: str, original_input: str) -> PlannedTask:
        """解析自然语言输出为PlannedTask"""
        try:
            logger.info("解析自然语言任务")

            # 清理markdown代码块
            cleaned = content.strip() if content else ""
            if cleaned.startswith("```"):
                end_idx = cleaned.find("```", 3)
                if end_idx > 0:
                    cleaned = cleaned[3:end_idx].strip()

            # 提取关键信息
            lines = cleaned.split('\n')
            task_id = f"task_{uuid.uuid4().hex[:8]}"
            description = original_input
            actor = "未知"
            target = None
            action = ""
            context: dict = {"raw_description": cleaned}

            for line in lines:
                line = line.strip()
                if line.startswith("任务ID:") or line.startswith("任务编号:"):
                    task_id = line.split(":", 1)[1].strip()
                elif line.startswith("任务描述:") or line.startswith("描述:"):
                    description = line.split(":", 1)[1].strip()
                elif line.startswith("行动者:") or line.startswith("执行者:"):
                    actor = line.split(":", 1)[1].strip()
                elif line.startswith("目标:"):
                    target = line.split(":", 1)[1].strip()
                elif line.startswith("动作:"):
                    action = line.split(":", 1)[1].strip()
                elif line.startswith("- 行动者状态:") or line.startswith("- 目标状态:"):
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        key = parts[1].strip().split()[0]
                        if "actor_key" not in context:
                            context["actor_key"] = key
                        else:
                            context["target_key"] = key

            # 如果没有提取到描述，使用原始输入的前缀
            if description == original_input and len(lines) > 0:
                # 取第一行非空且不是字段定义的行作为描述
                for line in lines:
                    line_stripped = line.strip()
                    if line_stripped and not line_stripped.startswith(("任务", "行动者", "目标", "动作", "执行", "- ", "* ")):
                        description = line_stripped
                        break

            task = PlannedTask(
                task_id=task_id,
                natural_description=description,
                actor=actor,
                target=target,
                action=action,
                context=context,
                source="dm"
            )

            logger.info(
                "生成任务",
                task_id=task.task_id,
                description=task.natural_description,
                actor=task.actor,
                target=task.target,
                action=task.action
            )

            return task

        except Exception as e:
            logger.error("解析失败", error=str(e), content=content[:500] if content else "None")
            # 失败时使用原始输入创建基本任务
            return PlannedTask(
                task_id=f"task_{uuid.uuid4().hex[:8]}",
                natural_description=original_input,
                actor="未知",
                context={"raw_description": content},
                source="dm"
            )
