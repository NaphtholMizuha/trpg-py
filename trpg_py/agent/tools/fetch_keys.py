from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from trpg_py.store import keys as list_state_keys


class FetchKeysError(BaseModel):
    type: str
    message: str


class FetchKeysResult(BaseModel):
    status: Literal["ok", "no_match", "error"]
    items: list[str] = Field(default_factory=list)
    error: FetchKeysError | None = None


class FetchKeysInput(BaseModel):
    prefix: str | None = Field(
        default=None,
        description="可选路径前缀；为空时返回全量可枚举路径。",
    )


class FetchKeysTool(BaseTool):
    name: str = "fetch_keys"
    description: str = (
        "枚举当前状态中可引用的点路径。"
        "不读取具体值、不写状态，只用于路径发现。"
    )
    args_schema: type[BaseModel] = FetchKeysInput

    state: Any = Field(exclude=True)
    state_provider: Callable[[], Any] | None = Field(default=None, exclude=True)

    def _run(self, prefix: str | None = None) -> dict[str, Any]:
        try:
            state = self._resolve_state()
            paths = list_state_keys(state, prefix=prefix)
            if not paths:
                return FetchKeysResult(status="no_match").model_dump(exclude_none=True)
            return FetchKeysResult(status="ok", items=paths).model_dump(exclude_none=True)
        except Exception as exc:
            return FetchKeysResult(
                status="error",
                error=FetchKeysError(type=exc.__class__.__name__, message=str(exc)),
            ).model_dump(exclude_none=True)

    def _resolve_state(self) -> Any:
        if self.state_provider is not None:
            return self.state_provider()
        return self.state


def create_fetch_keys_tool(
    *,
    state: Any | None = None,
    state_provider: Callable[[], Any] | None = None,
) -> FetchKeysTool:
    return FetchKeysTool(state={} if state is None else state, state_provider=state_provider)
