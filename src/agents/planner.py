"""
PlannerAgent - 规划Agent

合并意图识别 + RAG检索 + 任务生成
使用ReAct模式，通过tools决定如何执行
"""
import uuid
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import BaseTool

from ..config import PLANNER_SYSTEM_PROMPT
from ..types import PlannedTask
from ..utils.logging import get_logger
from .base import BaseAgent

logger = get_logger(__name__)

# 读取 prompt 文件
_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"
TASK_TEMPLATE = (_PROMPT_DIR / "planner_task.md").read_text(encoding="utf-8")
FORCE_OUTPUT_PROMPT = (_PROMPT_DIR / "force_output" / "planner.txt").read_text(encoding="utf-8")


class PlannerAgent(BaseAgent):
    """
    PlannerAgent - 规划Agent

    职责:
    1. 分析玩家输入的自然语言指令
    2. 使用fetch_keys查看所有可用的KV记忆key
    3. 使用read工具查询感兴趣的key的value
    4. 使用search工具(RAG)查询D&D规则
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

        # 使用模板构建任务提示
        task_prompt = TASK_TEMPLATE.format(user_input=user_input)

        # 构建对话历史
        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=task_prompt)
        ]

        # 使用基类的 ReAct 循环
        final_message = self._react_loop(
            messages,
            force_output_prompt=FORCE_OUTPUT_PROMPT
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

            # 如果没有提取到描述，使用原始输入
            if description == original_input and len(lines) > 0:
                for line in lines:
                    line_stripped = line.strip()
                    if line_stripped and not line_stripped.startswith(("任务", "行动者", "目标", "===", "- ", "* ")):
                        description = line_stripped
                        break

            task = PlannedTask(
                task_id=task_id,
                description=description,
                context=cleaned,
                actor=actor,
                target=target,
                source="dm"
            )

            logger.info(
                "生成任务",
                task_id=task.task_id,
                description=task.description,
                actor=task.actor,
                target=task.target
            )

            return task

        except Exception as e:
            logger.error("解析失败", error=str(e), content=content[:500] if content else "None")
            # 失败时使用原始输入创建基本任务
            return PlannedTask(
                task_id=f"task_{uuid.uuid4().hex[:8]}",
                description=original_input,
                context=content if content else "",
                actor="未知",
                source="dm"
            )

    # Note: plan_chain_task 方法已删除
    # 连锁任务现在通过 plan() 统一处理
    # dm_confirm_chain 将连锁触发转换为 HumanMessage，planner 像处理 DM 输入一样获取完整上下文
