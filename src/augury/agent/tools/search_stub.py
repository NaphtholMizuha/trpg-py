from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class SearchStubInput(BaseModel):
    query: str = Field(min_length=1)
    mode: str = "balanced"
    limit: int = 3
    fetch_k: int | None = None


class SearchStubTool(BaseTool):
    name: str = "search"
    description: str = "离线占位 search 工具；在未装配检索后端时稳定返回 no_match。"
    args_schema: type[BaseModel] = SearchStubInput

    reason: str = Field(default="search backend unavailable", exclude=True)

    def _run(
        self,
        query: str,
        mode: str = "balanced",
        limit: int = 3,
        fetch_k: int | None = None,
    ) -> dict[str, Any]:
        return {
            "status": "no_match",
            "hits": [],
            "meta": {
                "mode": mode,
                "limit": limit,
                "fetch_k": fetch_k,
                "reason": self.reason,
                "query": query,
            },
        }


def create_search_stub_tool(*, reason: str = "search backend unavailable") -> SearchStubTool:
    return SearchStubTool(reason=reason)
