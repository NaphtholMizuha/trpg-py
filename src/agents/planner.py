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
from ..types import PlannedTask, PotentialReaction
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
            potential_reactions: list[PotentialReaction] = []

            in_reaction_section = False
            for line in lines:
                line = line.strip()

                # 检测进入/离开"可能触发的反应"部分
                if "可能触发的反应" in line and "===" in line:
                    in_reaction_section = True
                    continue
                if in_reaction_section and line.startswith("==="):
                    in_reaction_section = False
                    continue

                # 解析反应条目
                if in_reaction_section and line.startswith("- [条件:"):
                    reaction = self._parse_reaction_line(line)
                    if reaction:
                        potential_reactions.append(reaction)

                # 提取基本信息
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
                source="dm",
                potential_reactions=potential_reactions
            )

            logger.info(
                "生成任务",
                task_id=task.task_id,
                description=task.description,
                actor=task.actor,
                target=task.target,
                reaction_count=len(potential_reactions)
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

    def _parse_reaction_line(self, line: str) -> PotentialReaction | None:
        """解析反应条目行

        格式: - [条件: 具体条件] [角色: 反应角色] [法术: 可能的反应法术] 反应描述
        示例: - [条件: 目标反应可用且准备有护盾术] [角色: 艾尔德拉] [法术: 护盾术] 可用护盾术免疫魔法飞弹
        """
        try:
            # 移除开头的 "- "
            line = line[2:].strip() if line.startswith("- ") else line.strip()

            # 解析 [条件: ...]
            condition = ""
            actor = ""
            spell = None
            description = ""

            # 提取各部分
            import re
            condition_match = re.search(r'\[条件:\s*([^\]]+)\]', line)
            actor_match = re.search(r'\[角色:\s*([^\]]+)\]', line)
            spell_match = re.search(r'\[法术:\s*([^\]]+)\]', line)

            if condition_match:
                condition = condition_match.group(1).strip()
            if actor_match:
                actor = actor_match.group(1).strip()
            if spell_match:
                spell = spell_match.group(1).strip()
                if spell == "无":
                    spell = None

            # 描述是最后一个 ] 之后的内容
            last_bracket = line.rfind(']')
            if last_bracket > 0:
                description = line[last_bracket + 1:].strip()

            # 如果条件是无，则返回 None
            if condition == "无":
                return None

            return PotentialReaction(
                condition=condition,
                actor=actor,
                spell=spell,
                description=description
            )

        except Exception as e:
            logger.warning("解析反应条目失败", line=line[:100], error=str(e))
            return None

    # Note: plan_chain_task 方法已删除
    # 连锁任务现在通过 plan() 统一处理
    # dm_confirm_chain 将连锁触发转换为 HumanMessage，planner 像处理 DM 输入一样获取完整上下文
