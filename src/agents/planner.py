"""
PlannerAgent - 规划Agent

合并意图识别 + RAG检索 + 任务生成
使用ReAct模式，通过tools决定如何执行
"""
import uuid
import re
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import BaseTool

from ..config import PLANNER_SYSTEM_PROMPT
from ..types import PlannedTask, PotentialChain
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
            action = ""
            actor_status = ""
            target_status = ""
            context: dict = {"raw_description": cleaned}
            potential_chains: list[PotentialChain] = []

            # 解析连锁相关标记
            in_chain_section = False

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
                elif line.startswith("- 行动者状态:"):
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        status_value = parts[1].strip()
                        actor_status = status_value
                        # 提取key（状态值的第一部分）
                        key = status_value.split()[0] if status_value else ""
                        if key:
                            context["actor_key"] = key
                elif line.startswith("- 目标状态:"):
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        status_value = parts[1].strip()
                        target_status = status_value
                        # 提取key（状态值的第一部分）
                        key = status_value.split()[0] if status_value else ""
                        if key:
                            context["target_key"] = key
                elif "可能触发的连锁" in line:
                    in_chain_section = True
                    continue
                elif in_chain_section and line.startswith("==="):
                    in_chain_section = False
                elif in_chain_section and line.startswith("-") and "[条件:" in line and "[类型:" in line:
                    # 解析连锁条目: - [条件: xxx] [类型: yyy] 描述
                    chain = self._parse_potential_chain_line(line)
                    if chain:
                        potential_chains.append(chain)

            # 如果没有提取到描述，使用原始输入的前缀
            if description == original_input and len(lines) > 0:
                # 取第一行非空且不是字段定义的行作为描述
                for line in lines:
                    line_stripped = line.strip()
                    if line_stripped and not line_stripped.startswith(("任务", "行动者", "目标", "动作", "执行", "- ", "* ")):
                        description = line_stripped
                        break

            # 确保 context 包含足够的信息供 Executor 使用
            context.update({
                "actor": actor,
                "target": target,
                "action": action,
                "actor_status": actor_status,
                "target_status": target_status
            })

            task = PlannedTask(
                task_id=task_id,
                natural_description=description,
                actor=actor,
                target=target,
                action=action,
                context=context,
                source="dm",
                potential_chains=potential_chains
            )

            logger.info(
                "生成任务",
                task_id=task.task_id,
                description=task.natural_description,
                actor=task.actor,
                target=task.target,
                action=task.action,
                potential_chains=len(task.potential_chains)
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

    def _parse_potential_chain_line(self, line: str) -> PotentialChain | None:
        """解析连锁条目行
        格式: - [条件: xxx] [类型: yyy] 描述
        """
        try:
            # 移除开头的 "- "
            line = line[2:].strip() if line.startswith("-") else line.strip()

            # 提取条件
            condition_match = re.search(r'\[条件:\s*([^\]]+)\]', line)
            condition = condition_match.group(1).strip() if condition_match else ""

            # 提取类型
            type_match = re.search(r'\[类型:\s*([^\]]+)\]', line)
            chain_type = type_match.group(1).strip() if type_match else "unknown"

            # 提取描述（类型标记之后的部分）
            description = line
            if type_match:
                # 找到类型标记的结束位置
                end_pos = type_match.end()
                description = line[end_pos:].strip()

            # 过滤掉"无"或空条目
            if not condition or condition == "无" or chain_type == "无":
                return None

            return PotentialChain(
                condition=condition,
                chain_type=chain_type,
                description=description
            )
        except Exception as e:
            logger.warning("解析连锁条目失败", line=line, error=str(e))
            return None

    def plan_chain_task(self, chain_trigger: dict, state: dict) -> PlannedTask | None:
        """根据连锁触发信息生成连锁任务

        Args:
            chain_trigger: 连锁触发信息，包含 type, description, source_key 等
            state: 当前状态

        Returns:
            生成的连锁任务，如果无法生成则返回 None
        """
        chain_type = chain_trigger.get("type", "unknown")
        description = chain_trigger.get("description", "")
        source_key = chain_trigger.get("source_key", "")

        logger.info("生成连锁任务", chain_type=chain_type, description=description)

        # 根据连锁类型生成任务
        task_id = f"chain_{uuid.uuid4().hex[:8]}"

        if chain_type == "death":
            # 死亡连锁：进行死亡豁免检定
            entity = source_key.split(".")[0] if "." in source_key else source_key
            return PlannedTask(
                task_id=task_id,
                natural_description=f"【连锁】{entity} HP降至0，需要进行死亡豁免检定",
                actor=entity,
                target=entity,
                action="死亡豁免检定",
                context={
                    "chain_type": chain_type,
                    "source_key": source_key,
                    "trigger_description": description
                },
                source="chain",
                requires_confirmation=True
            )
        elif chain_type == "explosion":
            # 爆炸连锁
            entity = source_key.split(".")[0] if "." in source_key else source_key
            return PlannedTask(
                task_id=task_id,
                natural_description=f"【连锁】{entity} 触发爆炸，计算爆炸伤害",
                actor=entity,
                target="周围10尺内所有生物",
                action="爆炸伤害",
                context={
                    "chain_type": chain_type,
                    "source_key": source_key,
                    "trigger_description": description,
                    "damage_dice": "3d6"  # 默认伤害骰
                },
                source="chain",
                requires_confirmation=True
            )
        elif chain_type == "collapse":
            # 坍塌连锁
            entity = source_key.split(".")[0] if "." in source_key else source_key
            return PlannedTask(
                task_id=task_id,
                natural_description=f"【连锁】{entity} 结构破坏，计算坍塌伤害",
                actor=entity,
                target="下方/周围生物",
                action="坍塌伤害",
                context={
                    "chain_type": chain_type,
                    "source_key": source_key,
                    "trigger_description": description
                },
                source="chain",
                requires_confirmation=True
            )
        else:
            # 其他类型的连锁，使用描述生成通用任务
            return PlannedTask(
                task_id=task_id,
                natural_description=f"【连锁】{description}",
                actor="系统",
                target=source_key,
                action="连锁处理",
                context={
                    "chain_type": chain_type,
                    "source_key": source_key,
                    "trigger_description": description
                },
                source="chain",
                requires_confirmation=True
            )
