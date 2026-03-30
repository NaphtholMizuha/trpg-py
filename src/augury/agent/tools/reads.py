from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from langchain_core.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field

from augury.agent.planner_runtime_guards import get_active_planner_runtime_guard
from augury.agent.tools.path_suggestions import merge_suggestions, suggest_paths
from augury.errors import StatePathError
from augury.store import keys as list_state_keys
from augury.store import read, reads as batch_read


class ReadError(BaseModel):
    type: str
    message: str


class ReadItem(BaseModel):
    path: str
    status: Literal["ok", "no_match"]
    value: Any = None
    suggestions: list[str] = Field(default_factory=list)
    error: ReadError | None = None


class ReadResult(BaseModel):
    status: Literal["ok", "no_match", "error"]
    items: list[ReadItem] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    error: ReadError | None = None


class ReadInput(BaseModel):
    paths: list[str] = Field(min_length=1, description="需要读取的一个或多个点路径。")


class ReadTool(BaseTool):
    name: str = "read"
    description: str = (
        "读取一个或多个点路径对应的当前状态值。"
        "只读、无副作用，不写状态也不执行任务。"
    )
    args_schema: type[BaseModel] = ReadInput

    state: Any = Field(exclude=True)
    state_provider: Callable[[], Any] | None = Field(default=None, exclude=True)

    def _run(self, paths: list[str]) -> dict[str, Any]:
        _log_read_input(paths=paths, tool_name=self.name)
        guard = get_active_planner_runtime_guard()
        if guard is not None:
            guarded_result = guard.short_circuit_read(tool_name=self.name, paths=paths)
            if guarded_result is not None:
                logger.warning(
                    "tool_guard tool={} kind=repeated_no_match paths={}",
                    self.name,
                    paths,
                )
                validated = ReadResult.model_validate(guarded_result)
                _log_read_output(validated, tool_name=self.name)
                return validated.model_dump(exclude_none=True)
        try:
            result = read_paths(self._resolve_state(), paths)
        except Exception as exc:
            result = ReadResult(
                status="error",
                error=ReadError(type=exc.__class__.__name__, message=str(exc)),
            )
        _log_read_output(result, tool_name=self.name)
        payload = result.model_dump(exclude_none=True)
        if guard is not None:
            guard.record_read_result(result=payload)
        return payload

    def _resolve_state(self) -> Any:
        if self.state_provider is not None:
            return self.state_provider()
        return self.state


class ReadsTool(ReadTool):
    name: str = "reads"


def read_paths(state: Any, paths: list[str]) -> ReadResult:
    normalized = [str(path) for path in paths]
    all_paths = list_state_keys(state)
    try:
        values = batch_read(state, normalized)
    except StatePathError:
        items: list[ReadItem] = []
        matched = 0
        suggestion_groups: list[list[str]] = []
        for path in normalized:
            try:
                value = read(state, path)
            except StatePathError as exc:
                suggestions = suggest_paths(all_paths, path)
                suggestion_groups.append(suggestions)
                items.append(
                    ReadItem(
                        path=path,
                        status="no_match",
                        suggestions=suggestions,
                        error=ReadError(type=exc.__class__.__name__, message=str(exc)),
                    )
                )
                continue
            matched += 1
            items.append(ReadItem(path=path, status="ok", value=value))
        return ReadResult(
            status="ok" if matched else "no_match",
            items=items,
            suggestions=merge_suggestions(suggestion_groups),
        )
    return ReadResult(
        status="ok",
        items=[ReadItem(path=path, status="ok", value=value) for path, value in zip(normalized, values, strict=True)],
    )


def create_read_tool(
    *,
    state: Any | None = None,
    state_provider: Callable[[], Any] | None = None,
) -> ReadTool:
    return ReadTool(state={} if state is None else state, state_provider=state_provider)


def create_reads_tool(
    *,
    state: Any | None = None,
    state_provider: Callable[[], Any] | None = None,
) -> ReadsTool:
    return ReadsTool(state={} if state is None else state, state_provider=state_provider)


def _log_read_input(*, paths: list[str], tool_name: str) -> None:
    logger.info("tool_input tool={} paths={} sample_paths={}", tool_name, len(paths), paths[:3])


def _log_read_output(result: ReadResult, *, tool_name: str) -> None:
    if result.status == "ok":
        logger.info(
            "tool_output tool={} status=ok items={} matched={}",
            tool_name,
            len(result.items),
            sum(1 for item in result.items if item.status == "ok"),
        )
        return
    if result.status == "no_match":
        logger.info(
            "tool_output tool={} status=no_match items={} suggestions={} sample_suggestions={}",
            tool_name,
            len(result.items),
            len(result.suggestions),
            result.suggestions[:3],
        )
        return
    logger.error(
        "tool_output tool={} status=error error_type={} error_message={!r}",
        tool_name,
        result.error.type if result.error else "unknown",
        result.error.message if result.error else "",
    )


ReadsError = ReadError
ReadsItem = ReadItem
ReadsResult = ReadResult
ReadsInput = ReadInput
