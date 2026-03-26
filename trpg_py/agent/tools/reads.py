from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from langchain_core.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field

from trpg_py.errors import StatePathError
from trpg_py.store import read, reads as batch_read


class ReadsError(BaseModel):
    type: str
    message: str


class ReadsItem(BaseModel):
    path: str
    status: Literal["ok", "no_match"]
    value: Any = None
    error: ReadsError | None = None


class ReadsResult(BaseModel):
    status: Literal["ok", "no_match", "error"]
    items: list[ReadsItem] = Field(default_factory=list)
    error: ReadsError | None = None


class ReadsInput(BaseModel):
    paths: list[str] = Field(min_length=1, description="需要读取的一个或多个点路径。")


class ReadsTool(BaseTool):
    name: str = "reads"
    description: str = (
        "读取一个或多个点路径对应的当前状态值。"
        "只读、无副作用，不写状态也不执行任务。"
    )
    args_schema: type[BaseModel] = ReadsInput

    state: Any = Field(exclude=True)
    state_provider: Callable[[], Any] | None = Field(default=None, exclude=True)

    def _run(self, paths: list[str]) -> dict[str, Any]:
        _log_reads_input(paths=paths)
        try:
            result = read_paths(self._resolve_state(), paths)
        except Exception as exc:
            result = ReadsResult(
                status="error",
                error=ReadsError(type=exc.__class__.__name__, message=str(exc)),
            )
        _log_reads_output(result)
        return result.model_dump(exclude_none=True)

    def _resolve_state(self) -> Any:
        if self.state_provider is not None:
            return self.state_provider()
        return self.state


def read_paths(state: Any, paths: list[str]) -> ReadsResult:
    normalized = [str(path) for path in paths]
    try:
        values = batch_read(state, normalized)
    except StatePathError:
        items: list[ReadsItem] = []
        matched = 0
        for path in normalized:
            try:
                value = read(state, path)
            except StatePathError as exc:
                items.append(
                    ReadsItem(
                        path=path,
                        status="no_match",
                        error=ReadsError(type=exc.__class__.__name__, message=str(exc)),
                    )
                )
                continue
            matched += 1
            items.append(ReadsItem(path=path, status="ok", value=value))
        return ReadsResult(status="ok" if matched else "no_match", items=items)
    return ReadsResult(
        status="ok",
        items=[ReadsItem(path=path, status="ok", value=value) for path, value in zip(normalized, values, strict=True)],
    )


def create_reads_tool(
    *,
    state: Any | None = None,
    state_provider: Callable[[], Any] | None = None,
) -> ReadsTool:
    return ReadsTool(state={} if state is None else state, state_provider=state_provider)


def _log_reads_input(*, paths: list[str]) -> None:
    logger.info("tool_input tool=reads paths={} sample_paths={}", len(paths), paths[:3])


def _log_reads_output(result: ReadsResult) -> None:
    if result.status == "ok":
        logger.info(
            "tool_output tool=reads status=ok items={} matched={}",
            len(result.items),
            sum(1 for item in result.items if item.status == "ok"),
        )
        return
    if result.status == "no_match":
        logger.info("tool_output tool=reads status=no_match items={}", len(result.items))
        return
    logger.error(
        "tool_output tool=reads status=error error_type={} error_message={!r}",
        result.error.type if result.error else "unknown",
        result.error.message if result.error else "",
    )
