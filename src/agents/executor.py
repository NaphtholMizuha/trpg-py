"""ExecutorAgent - 最小执行 Agent。"""
from __future__ import annotations

import json
import re
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import BaseTool

from ..config import EXECUTOR_SYSTEM_PROMPT
from ..types import PlannedTask, ExecutionResult, StateChange, Operation, StepUpdate, ProposedFragment
from ..utils.logging import get_logger
from .base import BaseAgent

logger = get_logger(__name__)

_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"
TASK_TEMPLATE = (_PROMPT_DIR / "executor_task.md").read_text(encoding="utf-8")
FORCE_OUTPUT_PROMPT = (_PROMPT_DIR / "force_output" / "executor.txt").read_text(encoding="utf-8")


class ExecutorAgent(BaseAgent):
    """执行单个步骤，并返回状态更新。"""

    SYSTEM_PROMPT = EXECUTOR_SYSTEM_PROMPT
    ALLOWED_TOOLS = {"evaluate", "write_fields"}

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
        tools: list[BaseTool] | None = None,
    ):
        filtered_tools = None
        if tools is not None:
            filtered_tools = [t for t in tools if t.name in self.ALLOWED_TOOLS]
        super().__init__(model, api_key, base_url, filtered_tools, max_iterations=4)

    def get_system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def execute(self, task: PlannedTask, execution_context: dict | None = None) -> ExecutionResult:
        logger.info("ExecutorAgent 执行任务", task_id=task.task_id, description=task.description)

        task_prompt = TASK_TEMPLATE.format(
            task_id=task.task_id,
            description=task.description,
            actor=task.actor,
            target=task.target,
            dm_notes=task.dm_notes or "无",
            context=task.context,
            execution_context=json.dumps(execution_context or {}, ensure_ascii=False, indent=2),
        )

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=task_prompt),
        ]
        final_message = self._react_loop(messages, force_output_prompt=FORCE_OUTPUT_PROMPT)

        content = ""
        if isinstance(final_message.content, str):
            content = final_message.content
        elif isinstance(final_message.content, list):
            content = "\n".join(str(item) for item in final_message.content)
        if "<think>" in content:
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        logger.info("LLM 输出", content=content[:200] if content else "None")
        return self._parse_execution_result(content, task, execution_context or {})

    def _parse_execution_result(
        self,
        content: str,
        task: PlannedTask,
        execution_context: dict[str, object],
    ) -> ExecutionResult:
        try:
            cleaned = content.strip() if content else ""
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            json_start = cleaned.find("{")
            json_end = cleaned.rfind("}")
            if json_start >= 0 and json_end > json_start:
                cleaned = cleaned[json_start:json_end + 1]

            data = json.loads(cleaned)

            field_changes = [
                self._parse_state_change(change, task.task_id)
                for change in (data.get("field_changes") or data.get("direct_changes") or [])
            ]
            step_updates = [
                StepUpdate(
                    step_id=item.get("step_id", ""),
                    status=item.get("status", "completed"),
                    note=item.get("note", ""),
                )
                for item in data.get("step_updates", [])
                if item.get("step_id")
            ]

            fragment_data = data.get("proposed_fragment")
            proposed_fragment = None
            if fragment_data and fragment_data.get("anchor_step_id"):
                proposed_fragment = ProposedFragment(
                    anchor_step_id=fragment_data.get("anchor_step_id", ""),
                    insert_position=fragment_data.get("insert_position", "after"),
                    reason=fragment_data.get("reason", ""),
                    fragment_summary=fragment_data.get("fragment_summary", ""),
                    required_context_keys=fragment_data.get("required_context_keys", []),
                    choice_title=fragment_data.get("choice_title"),
                    choice_prompt=fragment_data.get("choice_prompt"),
                )

            result = ExecutionResult(
                task_id=task.task_id,
                success=data.get("success", True),
                field_changes=field_changes,
                narration=data.get("narration", "执行完成"),
                step_updates=step_updates,
                proposed_fragment=proposed_fragment,
                triggered_chains=data.get("triggered_chains", []),
                execution_context=data.get("execution_context", {}),
            )
            result = self._sanitize_result(result, execution_context)
            if not self._is_actionable_result(result):
                logger.warning("Executor 输出为空结果，将标记为 stalled", active_step_id=execution_context.get("active_step_id"))
                result.success = False
                result.narration = "executor_stalled"
            return result
        except Exception as exc:
            logger.error("解析执行结果时出错", error=str(exc), content=content[:500] if content else "None")
            return self._build_fallback_result(task, execution_context)

    def _build_fallback_result(
        self,
        task: PlannedTask,
        execution_context: dict[str, object],
    ) -> ExecutionResult:
        if task.task_category == "world_edit":
            return ExecutionResult(
                task_id=task.task_id,
                success=True,
                field_changes=[],
                narration="世界编辑任务待人工确认",
            )

        return ExecutionResult(
            task_id=task.task_id,
            success=True,
            field_changes=[],
            narration="使用回退逻辑推进执行稿",
            step_updates=[StepUpdate(step_id=str(execution_context.get("active_step_id")), status="completed", note="fallback")] if execution_context.get("active_step_id") else [],
            triggered_chains=[],
        )

    def _parse_state_change(self, data: dict, task_id: str) -> StateChange:
        key = data.get("key", data.get("path", ""))
        field = data.get("field", "")
        path = f"{key}.{field}" if field and key else (key or field or "unknown")
        op_str = data.get("operation", "MOD")
        try:
            operation = Operation(op_str)
        except ValueError:
            operation = Operation.MOD
        return StateChange(
            path=path,
            old_value=data.get("old_value", ""),
            new_value=data.get("new_value", ""),
            operation=operation,
            source=task_id,
        )

    def _is_actionable_result(self, result: ExecutionResult) -> bool:
        return any(
            (
                result.field_changes,
                result.step_updates,
                result.triggered_chains,
            )
        )

    def _sanitize_result(self, result: ExecutionResult, execution_context: dict[str, object]) -> ExecutionResult:
        active_step_id = str(execution_context.get("active_step_id") or "")
        active_step = execution_context.get("active_step") or {}
        active_phase = str(active_step.get("phase") or "")
        relevant_keys = set(execution_context.get("relevant_keys") or [])

        if active_step_id:
            result.step_updates = [item for item in result.step_updates if item.step_id == active_step_id][:1]

        result.field_changes = [
            change for change in result.field_changes
            if self._is_valid_world_state_change(change.path, relevant_keys)
        ]

        if active_phase == "choice":
            result.field_changes = []

        result.proposed_fragment = None

        return result

    def _is_valid_world_state_change(self, path: str, relevant_keys: set[str]) -> bool:
        if not path or path.startswith("task_"):
            return False
        key = path.rsplit(".", 1)[0] if "." in path else path
        return not relevant_keys or key in relevant_keys

    def run(self, task: PlannedTask) -> ExecutionResult:
        return self.execute(task)
