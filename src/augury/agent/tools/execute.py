from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from copy import deepcopy
from typing import Any, Literal

from langchain_core.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field

from augury.engine.core.dice import DiceRoller
from augury.engine.core.executor import execute_task


class ExecuteError(BaseModel):
    type: str
    message: str


class ExecuteInput(BaseModel):
    task_document: dict[str, Any]


class ExecuteResult(BaseModel):
    status: Literal["success", "validation_failed", "failed", "error"]
    execution_report: dict[str, Any] | None = None
    state_changes: list[dict[str, Any]] = Field(default_factory=list)
    error: ExecuteError | None = None


class ExecuteTool(BaseTool):
    name: str = "execute"
    description: str = "复用现有引擎执行链路执行 TaskDocument，并返回结构化执行报告。"
    args_schema: type[BaseModel] = ExecuteInput

    state: dict[str, Any] = Field(exclude=True)
    state_provider: Callable[[], dict[str, Any]] | None = Field(default=None, exclude=True)
    roller: DiceRoller | None = Field(default=None, exclude=True)

    def _run(self, task_document: dict[str, Any]) -> dict[str, Any]:
        task_id = task_document.get("task_id")
        steps = task_document.get("steps", [])
        logger.info(
            "tool_input tool=execute task_id={!r} steps={}",
            task_id,
            len(steps) if isinstance(steps, list) else 0,
        )
        try:
            state = self._resolve_state()
            report = execute_task(task_document, state, roller=self.roller)
            result = ExecuteResult(
                status=_map_execution_status(report.status),
                execution_report=report.to_dict(),
                state_changes=[asdict(change) for change in report.applied_changes],
            )
        except Exception as exc:
            result = ExecuteResult(
                status="error",
                error=ExecuteError(type=exc.__class__.__name__, message=str(exc)),
            )
        _log_execute_output(result, task_id=task_id)
        return result.model_dump(exclude_none=True)

    def _resolve_state(self) -> dict[str, Any]:
        if self.state_provider is not None:
            return self.state_provider()
        return self.state


def create_execute_tool(
    *,
    state: dict[str, Any] | None = None,
    state_provider: Callable[[], dict[str, Any]] | None = None,
    roller: DiceRoller | None = None,
) -> ExecuteTool:
    return ExecuteTool(
        state={} if state is None else state,
        state_provider=state_provider,
        roller=roller,
    )


def execute_document(
    task_document: dict[str, Any],
    *,
    state: dict[str, Any],
    roller: DiceRoller | None = None,
) -> ExecuteResult:
    tool = create_execute_tool(state=state, roller=roller)
    return ExecuteResult.model_validate(tool.invoke({"task_document": deepcopy(task_document)}))


def _map_execution_status(status: str) -> Literal["success", "validation_failed", "failed", "error"]:
    if status == "success":
        return "success"
    if status == "validation_failed":
        return "validation_failed"
    if status == "failed":
        return "failed"
    return "error"


def _log_execute_output(result: ExecuteResult, *, task_id: Any) -> None:
    if result.status in {"success", "validation_failed", "failed"}:
        logger.info(
            "tool_output tool=execute status={} task_id={!r} state_changes={}",
            result.status,
            task_id,
            len(result.state_changes),
        )
        return
    logger.error(
        "tool_output tool=execute status=error task_id={!r} error_type={} error_message={!r}",
        task_id,
        result.error.type if result.error else "unknown",
        result.error.message if result.error else "",
    )
