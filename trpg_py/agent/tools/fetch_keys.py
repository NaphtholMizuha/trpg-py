from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from langchain_core.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field

from trpg_py.agent.planner_runtime_guards import get_active_planner_runtime_guard
from trpg_py.agent.tools.path_suggestions import suggest_paths
from trpg_py.store import keys as list_state_keys


class ListError(BaseModel):
    type: str
    message: str


class ListResult(BaseModel):
    status: Literal["ok", "no_match", "error"]
    items: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    error: ListError | None = None


class ListInput(BaseModel):
    prefix: str | None = Field(
        default=None,
        description="可选路径前缀；为空时返回全量可枚举路径。",
    )


class ListTool(BaseTool):
    name: str = "list"
    description: str = (
        "枚举当前状态中可引用的点路径。"
        "不读取具体值、不写状态，只用于路径发现。"
    )
    args_schema: type[BaseModel] = ListInput

    state: Any = Field(exclude=True)
    state_provider: Callable[[], Any] | None = Field(default=None, exclude=True)

    def _run(self, prefix: str | None = None) -> dict[str, Any]:
        _log_list_input(prefix=prefix, tool_name=self.name)
        guard = get_active_planner_runtime_guard()
        if guard is not None:
            guarded_result = guard.short_circuit_list(tool_name=self.name, prefix=prefix)
            if guarded_result is not None:
                logger.warning(
                    "tool_guard tool={} kind=repeated_no_match prefix={!r}",
                    self.name,
                    prefix,
                )
                validated = ListResult.model_validate(guarded_result)
                _log_list_output(validated, tool_name=self.name)
                return validated.model_dump(exclude_none=True)
        try:
            state = self._resolve_state()
            all_paths = list_state_keys(state)
            paths = list_state_keys(state, prefix=prefix)
            if not paths:
                result = ListResult(
                    status="no_match",
                    suggestions=suggest_paths(all_paths, prefix),
                )
                _log_list_output(result, tool_name=self.name)
                payload = result.model_dump(exclude_none=True)
                if guard is not None:
                    guard.record_list_result(prefix=prefix, result=payload)
                return payload
            result = ListResult(status="ok", items=paths)
            _log_list_output(result, tool_name=self.name)
            payload = result.model_dump(exclude_none=True)
            if guard is not None:
                guard.record_list_result(prefix=prefix, result=payload)
            return payload
        except Exception as exc:
            result = ListResult(
                status="error",
                error=ListError(type=exc.__class__.__name__, message=str(exc)),
            )
            _log_list_output(result, tool_name=self.name)
            return result.model_dump(exclude_none=True)

    def _resolve_state(self) -> Any:
        if self.state_provider is not None:
            return self.state_provider()
        return self.state


class FetchKeysTool(ListTool):
    name: str = "fetch_keys"


def create_list_tool(
    *,
    state: Any | None = None,
    state_provider: Callable[[], Any] | None = None,
) -> ListTool:
    return ListTool(state={} if state is None else state, state_provider=state_provider)


def create_fetch_keys_tool(
    *,
    state: Any | None = None,
    state_provider: Callable[[], Any] | None = None,
) -> FetchKeysTool:
    return FetchKeysTool(state={} if state is None else state, state_provider=state_provider)


def _log_list_input(*, prefix: str | None, tool_name: str) -> None:
    logger.info("tool_input tool={} prefix={!r}", tool_name, prefix)


def _log_list_output(result: ListResult, *, tool_name: str) -> None:
    if result.status == "ok":
        logger.info(
            "tool_output tool={} status=ok items={} sample_paths={}",
            tool_name,
            len(result.items),
            result.items[:3],
        )
        return
    if result.status == "no_match":
        logger.info(
            "tool_output tool={} status=no_match items=0 suggestions={} sample_suggestions={}",
            tool_name,
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


FetchKeysError = ListError
FetchKeysResult = ListResult
FetchKeysInput = ListInput
