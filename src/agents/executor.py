"""
ExecutorAgent - 执行Agent

合并逻辑计算 + 状态写入
使用ReAct模式，通过tools执行计算和写入
"""
import uuid
import json

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import BaseTool

from ..config import EXECUTOR_SYSTEM_PROMPT
from ..types import PlannedTask, ExecutionResult, StateChange
from ..utils.logging import get_logger
from .base import BaseAgent

logger = get_logger(__name__)


class ExecutorAgent(BaseAgent):
    """
    ExecutorAgent - 执行Agent

    职责:
    1. 分析PlannerAgent生成的自然语言任务描述
    2. 使用evaluate工具执行表达式计算（含Roll）
    3. 使用write工具修改KV记忆
    4. 返回执行结果

    如果不能确定计算逻辑，回滚到DM确认
    """

    SYSTEM_PROMPT = EXECUTOR_SYSTEM_PROMPT

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

    def execute(self, task: PlannedTask) -> ExecutionResult:
        """
        执行PlannedTask

        使用ReAct模式:
        1. 调用LLM生成tool calls
        2. 执行tools计算和写入
        3. 返回执行结果
        """
        logger.info("ExecutorAgent 执行任务", task_id=task.task_id, description=task.natural_description)

        # 构建对话历史
        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=f"""请执行以下任务:

任务ID: {task.task_id}
任务描述: {task.natural_description}
行动者: {task.actor}
目标: {task.target}
动作: {task.action}

任务详情:
{task.context.get('raw_description', '无详细描述')}

工作流程：
1. 使用fetch_keys查看可用key，使用read读取相关状态
2. 使用evaluate执行掷骰和计算
3. 根据结果生成JSON格式的变更指令
4. 使用write工具执行状态变更
5. 输出JSON格式的执行结果

重要：
- 攻击未命中时changes设为空数组，不调用write
- 只能修改已存在的key
- new_value必须是完整的自然语言段落
- 输出必须是JSON格式，包含success, narration, changes字段
""")
        ]

        # 使用基类的 ReAct 循环
        final_message = self._react_loop(
            messages,
            force_output_prompt='请直接输出JSON格式的执行结果，格式为 {"success": true/false, "narration": "...", "changes": [...]}，不要继续调用工具。'
        )

        content_str = ""
        if isinstance(final_message.content, str):
            content_str = final_message.content
        elif isinstance(final_message.content, list):
            content_str = "\n".join(str(item) for item in final_message.content)

        logger.info("LLM 输出", content=content_str[:200] if content_str else "None")
        return self._parse_execution_result(content_str, task)

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

            # 解析changes
            changes = []
            for c in data.get("changes", []):
                changes.append(StateChange(
                    path=c.get("path", c.get("key", "")),
                    old_value=c.get("old_value"),
                    new_value=c.get("new_value"),
                    operation=c.get("operation", "MOD")
                ))

            result = ExecutionResult(
                task_id=task.task_id,
                success=data.get("success", True),
                changes=changes,
                narration=data.get("narration", "执行完成")
            )

            logger.info(
                "执行结果",
                narration=result.narration[:100],
                change_count=len(result.changes)
            )

            return result

        except Exception as e:
            logger.error("解析执行结果时出错", error=str(e), content=content[:500] if content else "None")
            # 返回基本结果
            return ExecutionResult(
                task_id=task.task_id,
                success=True,
                changes=[],
                narration=content[:500] if content else "执行完成"
            )
