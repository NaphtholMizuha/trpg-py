"""
ChainAgent - 连锁Agent，检测状态变更触发的连锁反应

V4版本: 统一自然语言任务队列，不再强制JSON输出
"""
import uuid
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import BaseTool

from ..config import CHAIN_SYSTEM_PROMPT
from ..types import StateChange, PlannedTask
from ..utils.logging import get_logger
from .base import BaseAgent

logger = get_logger(__name__)


class ChainAgent(BaseAgent):
    """
    ChainAgent - 连锁Agent (V3增强版)

    职责:
    1. 检查本轮的修改记录
    2. 使用read工具获取相关状态
    3. 使用search工具查询连锁相关规则（如死亡规则、爆炸规则等）
    4. 生成自然语言的连锁触发效果
    5. **置入任务队列前需要DM审批**（关键新增）

    DM审批机制:
    - ChainAgent生成连锁任务但不直接放入队列
    - 设置pending_chain_tasks等待DM确认
    - DM确认后才真正加入task_queue
    """

    SYSTEM_PROMPT = CHAIN_SYSTEM_PROMPT

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
        tools: list[BaseTool] | None = None
    ):
        super().__init__(model, api_key, base_url, tools, max_iterations=5)

    def get_system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def _format_changes_natural(self, changes: list[StateChange]) -> str:
        """将状态变更格式化为自然语言描述"""
        if not changes:
            return "无状态变更"

        lines = ["本轮状态变更："]
        for c in changes[-5:]:  # 最近5个变更
            old_val = str(c.old_value)[:50] if c.old_value else "None"
            new_val = str(c.new_value)[:50] if c.new_value else "None"
            lines.append(f"- {c.path}: {old_val} → {new_val} ({c.operation})")
        return "\n".join(lines)

    def check_chains(self, changes: list[StateChange], state_text: str) -> list[PlannedTask]:
        """
        检查状态变更的连锁反应，返回自然语言任务列表

        返回:
            list[PlannedTask]: 待审批的连锁任务列表（自然语言描述）
        """
        logger.info("ChainAgent 检测连锁反应")

        # 构建自然语言变更描述
        changes_desc = self._format_changes_natural(changes)

        # 构建对话历史
        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=f"""{changes_desc}

当前状态摘要:
{state_text[:800] if state_text else "状态未提供"}

请检测是否有连锁反应。

工作流程：
1. 使用工具查询需要的信息（fetch_keys/read/search）
2. 分析状态变更是否触发连锁
3. 用自然语言输出连锁检测结果（不要输出JSON）

如果没有连锁反应，直接输出"无连锁反应"。
""")
        ]

        # 使用基类的 ReAct 循环
        final_message = self._react_loop(
            messages,
            force_output_prompt="请直接输出自然语言格式的连锁检测结果，不要继续调用工具。"
        )

        content_str = ""
        if isinstance(final_message.content, str):
            content_str = final_message.content
        elif isinstance(final_message.content, list):
            content_str = "\n".join(str(item) for item in final_message.content)

        logger.info("LLM 输出", content=content_str[:200] if content_str else "None")
        return self._parse_natural_chain_result(content_str)

    def _is_valid_chain_task(self, text: str) -> bool:
        """判断文本是否是一个有效的连锁任务（只保留规则强制效果）"""
        # 过滤掉DM建议/确认类内容
        suggestion_keywords = [
            "DM应该", "DM应", "DM需要", "DM可以", "建议",
            "确认", "检查", "考虑", "询问玩家", "询问",
            "宣布", "描述", "提醒"
        ]
        for kw in suggestion_keywords:
            if kw in text:
                return False

        # 过滤掉只是观察/分析的行
        observation_keywords = [
            "没有降到", "没有变化", "仍然是", "当前", "状态为",
            "没有触发", "未达到", "不满足", "无连锁", "无需"
        ]
        for kw in observation_keywords:
            if kw in text:
                return False

        # 必须包含规则强制的自动效果关键词
        auto_effect_keywords = [
            "立即", "陷入", "进入", "死亡", "昏迷", "爆炸",
            "移除", "失效", "结束", "触发", "豁免", "失败"
        ]
        has_auto_effect = any(kw in text for kw in auto_effect_keywords)

        # 过滤掉环境描述类（如果文本只包含环境相关词汇）
        if all(kw in text for kw in ["遮蔽", "区域"]) or text.count("位置") > 2:
            return False

        return has_auto_effect and len(text) > 10

    def _parse_natural_chain_result(self, content: Any) -> list[PlannedTask]:
        """解析自然语言连锁检测结果为任务列表"""
        try:
            logger.info("解析自然语言连锁结果")

            # 确保content是字符串
            if not isinstance(content, str):
                content = str(content)

            # 清理markdown代码块
            cleaned = content.strip()
            if cleaned.startswith("```"):
                end_idx = cleaned.find("```", 3)
                if end_idx > 0:
                    cleaned = cleaned[3:end_idx].strip()

            tasks: list[PlannedTask] = []

            # 检查是否有"无连锁反应"或空触发器
            if "无连锁" in cleaned[:100] or cleaned[:10].strip() in ("无", "无连锁反应"):
                return tasks

            # 解析任务描述（严格只在"检测到以下连锁反应"段落中查找）
            lines = cleaned.split('\n')
            current_task_lines: list[str] = []
            in_detection_section = False  # 是否在"检测到以下连锁反应"段落中

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # 检测任务列表开始标记
                if "检测到以下连锁反应" in line:
                    in_detection_section = True
                    continue

                # 如果在检测段落外，跳过
                if not in_detection_section:
                    continue

                # 检测新任务开始 (格式: "1. ..." 或 "2. ...")
                if line[0].isdigit() and "." in line[:5]:
                    # 保存之前的任务
                    if current_task_lines:
                        task_desc = " ".join(current_task_lines).strip()
                        if self._is_valid_chain_task(task_desc):
                            tasks.append(PlannedTask(
                                task_id=f"chain_{uuid.uuid4().hex[:8]}",
                                natural_description=task_desc,
                                actor=None,
                                target=None,
                                action="连锁反应",
                                source="chain"
                            ))

                    # 开始新任务 - 提取任务描述（去掉编号）
                    task_start = line.find(".") + 1
                    task_text = line[task_start:].strip()
                    # 去掉优先级标记 [优先级X] 或 [优先级:X]
                    if task_text.startswith("[") and "]" in task_text:
                        task_text = task_text.split("]", 1)[1].strip()
                    current_task_lines = [task_text] if task_text else []

                # 解析子行（效果、执行任务等）
                elif current_task_lines:
                    if line.startswith("效果:") or line.startswith("执行任务") or line.startswith("-"):
                        current_task_lines.append(line)

            # 保存最后一个任务
            if current_task_lines:
                task_desc = " ".join(current_task_lines).strip()
                if self._is_valid_chain_task(task_desc):
                    tasks.append(PlannedTask(
                        task_id=f"chain_{uuid.uuid4().hex[:8]}",
                        natural_description=task_desc,
                        actor=None,
                        target=None,
                        action="连锁反应",
                        source="chain"
                    ))

            if tasks:
                logger.info(f"发现 {len(tasks)} 个连锁任务")
                for t in tasks:
                    logger.info(f"连锁任务: {t.natural_description[:60]}")
            else:
                logger.info("无有效连锁任务")

            return tasks

        except Exception as e:
            logger.error("解析连锁结果时出错", error=str(e))
            return []
