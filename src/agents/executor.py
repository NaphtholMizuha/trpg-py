"""
ExecutorAgent - 执行Agent (V2版本)

职责分离：只负责计算，不直接写入KV状态
- 使用查询工具（search/evaluate/fetch_keys/read）获取信息
- 生成字段级变更指令（field_changes）供 Writer 节点使用
- 检测简单连锁条件并返回触发信息

使用ReAct模式，通过tools执行计算
"""
import uuid
import json
import re
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import BaseTool

from ..config import EXECUTOR_SYSTEM_PROMPT
from ..types import PlannedTask, ExecutionResult, FieldChange
from ..utils.logging import get_logger
from .base import BaseAgent

logger = get_logger(__name__)

# 读取 prompt 文件
_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"
TASK_TEMPLATE = (_PROMPT_DIR / "executor_task.md").read_text(encoding="utf-8")
FORCE_OUTPUT_PROMPT = (_PROMPT_DIR / "force_output" / "executor.txt").read_text(encoding="utf-8")


class ExecutorAgent(BaseAgent):
    """
    ExecutorAgent - 执行Agent (V2版本)

    职责:
    1. 分析PlannerAgent生成的自然语言任务描述
    2. 使用evaluate工具执行表达式计算（含Roll）
    3. 使用read/fetch_keys工具查询当前状态（只读）
    4. 生成字段级变更指令（field_changes）给Writer节点使用
    5. 检测简单连锁条件并返回触发信息

    注意：本Agent不直接写入KV状态，只输出变更指令
    写入操作由独立的Writer节点负责（读取→合并→写入）

    如果不能确定计算逻辑，回滚到DM确认
    """

    SYSTEM_PROMPT = EXECUTOR_SYSTEM_PROMPT

    # Executor 只使用 evaluate 计算工具和 write_fields 写入工具
    ALLOWED_TOOLS = {"evaluate", "write_fields"}

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
        tools: list[BaseTool] | None = None
    ):
        # 过滤工具：只保留查询工具，移除 write 工具
        filtered_tools = None
        if tools is not None:
            filtered_tools = [t for t in tools if t.name in self.ALLOWED_TOOLS]
            removed = [t.name for t in tools if t.name not in self.ALLOWED_TOOLS]
            if removed:
                logger.debug(f"ExecutorAgent 过滤掉非查询工具: {removed}")

        super().__init__(model, api_key, base_url, filtered_tools, max_iterations=10)

    def get_system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def execute(self, task: PlannedTask) -> ExecutionResult:
        """
        执行PlannedTask

        使用ReAct模式:
        1. 调用LLM生成tool calls
        2. 执行tools计算
        3. 解析生成的field_changes
        4. 检测连锁条件
        5. 返回执行结果
        """
        logger.info("ExecutorAgent 执行任务", task_id=task.task_id, description=task.natural_description)

        # 使用模板构建任务提示
        task_prompt = TASK_TEMPLATE.format(
            task_id=task.task_id,
            natural_description=task.natural_description,
            actor=task.actor,
            target=task.target,
            action=task.action,
            dm_notes=task.dm_notes or "无",
            raw_description=task.context.get('raw_description', '无详细描述')
        )

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

        # 解析执行结果（LLM已返回triggered_chains，无需二次检测）
        result = self._parse_execution_result(content_str, task)

        if result.triggered_chains:
            logger.info("LLM检测到连锁触发", chains=[c["type"] for c in result.triggered_chains])

        return result

    def _parse_execution_result(self, content: str, task: PlannedTask) -> ExecutionResult:
        """解析JSON输出为ExecutionResult"""
        try:
            logger.info("解析执行结果")

            # 清理markdown代码块
            cleaned = content.strip() if content else ""
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            # 找到JSON部分
            json_start = cleaned.find("{")
            json_end = cleaned.rfind("}")
            if json_start >= 0 and json_end > json_start:
                cleaned = cleaned[json_start:json_end+1]
            else:
                raise ValueError(f"No JSON object found in content: {cleaned[:200]}")

            data = json.loads(cleaned)

            # 解析field_changes（优先）或changes
            field_changes = []
            changes_data = data.get("field_changes") or data.get("changes", [])
            for c in changes_data:
                field_changes.append(FieldChange(
                    key=c.get("key", c.get("path", "")),
                    field=c.get("field", "value"),
                    old_value=str(c.get("old_value", "")),
                    new_value=str(c.get("new_value", "")),
                    operation=c.get("operation", "MOD")
                ))

            result = ExecutionResult(
                task_id=task.task_id,
                success=data.get("success", True),
                field_changes=field_changes,
                narration=data.get("narration", "执行完成"),
                triggered_chains=data.get("triggered_chains", [])
            )

            logger.info(
                "执行结果解析完成",
                narration=result.narration[:100],
                change_count=len(result.field_changes),
                triggered_chains_count=len(result.triggered_chains)
            )

            return result

        except Exception as e:
            logger.error("解析执行结果时出错", error=str(e), content=content[:500] if content else "None")
            # 返回基本结果
            return ExecutionResult(
                task_id=task.task_id,
                success=True,
                field_changes=[],
                narration=content[:500] if content else "执行完成",
                triggered_chains=[]
            )

    def run(self, task: PlannedTask) -> ExecutionResult:
        """
        执行任务的入口方法（execute 的别名）

        遵循设计规范：
        - 只使用查询工具（search/evaluate/fetch_keys/read）
        - 不直接写入 KV 状态
        - 返回包含 field_changes 的 ExecutionResult

        Args:
            task: PlannedTask 任务对象

        Returns:
            ExecutionResult 包含字段级变更指令，供 Writer 节点使用
        """
        return self.execute(task)
