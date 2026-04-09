from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from langchain_core.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field

from augury.agent.tools.path_suggestions import merge_suggestions, suggest_paths
from augury.store import keys as list_state_keys


class ListError(BaseModel):
    type: str
    message: str


class ListResult(BaseModel):
    status: Literal["ok", "no_match", "error"]
    items: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    error: ListError | None = None


class ListInput(BaseModel):
    prefix: str | None = Field(default=None, description="可选前缀；为空时返回全部叶子路径。")


class ListTool(BaseTool):
    name: str = "list"
    description: str = "返回当前状态中可读写的全部叶子路径，支持按 prefix 过滤。"
    args_schema: type[BaseModel] = ListInput

    state: Any = Field(exclude=True)
    state_provider: Callable[[], Any] | None = Field(default=None, exclude=True)

    def _run(self, prefix: str | None = None) -> dict[str, Any]:
        normalized_prefix = prefix.strip() if isinstance(prefix, str) else None
        logger.info("tool_input tool=list prefix={}", normalized_prefix or None)
        try:
            result = list_paths(self._resolve_state(), prefix=normalized_prefix)
        except Exception as exc:
            result = ListResult(
                status="error",
                error=ListError(type=exc.__class__.__name__, message=str(exc)),
            )
        _log_list_output(result)
        return result.model_dump(exclude_none=True)

    def _resolve_state(self) -> Any:
        if self.state_provider is not None:
            return self.state_provider()
        return self.state


def list_paths(state: Any, *, prefix: str | None = None) -> ListResult:
    all_paths = list_state_keys(state)
    items = list_state_keys(state, prefix=prefix)
    if items:
        return ListResult(status="ok", items=items)
    suggestions = merge_suggestions([suggest_paths(all_paths, prefix or "")]) if prefix else all_paths[:10]
    return ListResult(status="no_match", items=[], suggestions=suggestions)


def create_list_tool(
    *,
    state: Any | None = None,
    state_provider: Callable[[], Any] | None = None,
) -> ListTool:
    return ListTool(state={} if state is None else state, state_provider=state_provider)


def _log_list_output(result: ListResult) -> None:
    if result.status == "ok":
        logger.info("tool_output tool=list status=ok items={}", len(result.items))
        return
    if result.status == "no_match":
        logger.info(
            "tool_output tool=list status=no_match items={} suggestions={} sample_suggestions={}",
            len(result.items),
            len(result.suggestions),
            result.suggestions[:3],
        )
        return
    logger.error(
        "tool_output tool=list status=error error_type={} error_message={!r}",
        result.error.type if result.error else "unknown",
        result.error.message if result.error else "",
    )
