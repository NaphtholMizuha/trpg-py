from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field


class PlannerGuardEvent(BaseModel):
    kind: Literal["repeated_no_match", "repeated_theme", "tool_budget_exhausted"]
    tool: str
    theme: str | None = None
    detail: str


@dataclass
class PlannerRuntimeGuard:
    list_no_match_suggestions: dict[str, list[str]] = field(default_factory=dict)
    read_no_match_suggestions: dict[str, list[str]] = field(default_factory=dict)
    grep_theme_results: dict[str, dict[str, object]] = field(default_factory=dict)
    search_theme_results: dict[str, dict[str, object]] = field(default_factory=dict)
    events: list[PlannerGuardEvent] = field(default_factory=list)

    def short_circuit_grep(self, *, tool_name: str, theme: str | None) -> dict[str, object] | None:
        normalized_theme = _normalize_theme(theme)
        if normalized_theme == "*":
            return None
        cached = self.grep_theme_results.get(normalized_theme)
        if cached is None:
            return None
        self.events.append(
            PlannerGuardEvent(
                kind="repeated_theme",
                tool=tool_name,
                theme=normalized_theme,
                detail=(
                    f"{tool_name} already returned a result for theme {normalized_theme!r}. "
                    "Reuse that result instead of querying the same theme again in this evidence run."
                ),
            )
        )
        return cached

    def record_grep_result(self, *, theme: str | None, result: dict[str, object]) -> None:
        normalized_theme = _normalize_theme(theme)
        if normalized_theme == "*":
            return
        if result.get("status") not in {"ok", "no_match"}:
            return
        self.grep_theme_results[normalized_theme] = result

    def short_circuit_search(self, *, tool_name: str, theme: str | None) -> dict[str, object] | None:
        normalized_theme = _normalize_theme(theme)
        if normalized_theme == "*":
            return None
        cached = self.search_theme_results.get(normalized_theme)
        if cached is None:
            return None
        self.events.append(
            PlannerGuardEvent(
                kind="repeated_theme",
                tool=tool_name,
                theme=normalized_theme,
                detail=(
                    f"{tool_name} already returned a result for theme {normalized_theme!r}. "
                    "Reuse that result instead of repeating the same rule lookup in this evidence run."
                ),
            )
        )
        return cached

    def record_search_result(self, *, theme: str | None, result: dict[str, object]) -> None:
        normalized_theme = _normalize_theme(theme)
        if normalized_theme == "*":
            return
        if result.get("status") not in {"ok", "no_match"}:
            return
        self.search_theme_results[normalized_theme] = result

    def short_circuit_list(self, *, tool_name: str, prefix: str | None) -> dict[str, object] | None:
        theme = _normalize_prefix(prefix)
        suggestions = self.list_no_match_suggestions.get(theme)
        if suggestions is None:
            return None
        self.events.append(
            PlannerGuardEvent(
                kind="repeated_no_match",
                tool=tool_name,
                theme=theme,
                detail=(
                    f"{tool_name} already returned no_match for prefix {theme!r}. "
                    "Treat the missing path as absent and stop retrying the same prefix."
                ),
            )
        )
        return {
            "status": "no_match",
            "items": [],
            "suggestions": list(suggestions),
        }

    def record_list_result(self, *, prefix: str | None, result: dict[str, object]) -> None:
        if result.get("status") != "no_match":
            return
        suggestions = [str(item) for item in result.get("suggestions", []) if item]
        self.list_no_match_suggestions[_normalize_prefix(prefix)] = suggestions

    def short_circuit_read(self, *, tool_name: str, paths: list[str]) -> dict[str, object] | None:
        normalized_paths = [str(path) for path in paths]
        if not normalized_paths:
            return None
        if any(path not in self.read_no_match_suggestions for path in normalized_paths):
            return None

        suggestion_groups = [self.read_no_match_suggestions[path] for path in normalized_paths]
        self.events.append(
            PlannerGuardEvent(
                kind="repeated_no_match",
                tool=tool_name,
                theme=", ".join(normalized_paths),
                detail=(
                    f"{tool_name} already returned no_match for paths {normalized_paths!r}. "
                    "Treat those missing values as absent and stop retrying the same reads."
                ),
            )
        )
        return {
            "status": "no_match",
            "items": [
                {
                    "path": path,
                    "status": "no_match",
                    "suggestions": list(self.read_no_match_suggestions[path]),
                }
                for path in normalized_paths
            ],
            "suggestions": _merge_suggestions(suggestion_groups),
        }

    def record_read_result(self, *, result: dict[str, object]) -> None:
        if result.get("status") not in {"ok", "no_match"}:
            return
        for item in result.get("items", []):
            if not isinstance(item, dict) or item.get("status") != "no_match":
                continue
            path = str(item.get("path", "")).strip()
            if not path:
                continue
            suggestions = [str(candidate) for candidate in item.get("suggestions", []) if candidate]
            self.read_no_match_suggestions[path] = suggestions

    def record_tool_budget_exhausted(
        self,
        *,
        tool_name: str | None,
        run_limit: int | None,
        run_count: int,
    ) -> None:
        tool_label = tool_name or "all-tools"
        self.events.append(
            PlannerGuardEvent(
                kind="tool_budget_exhausted",
                tool=tool_label,
                theme=tool_label,
                detail=(
                    f"tool budget exhausted after {run_count} attempted calls"
                    + (f" (limit={run_limit})" if run_limit is not None else "")
                ),
            )
        )


_ACTIVE_PLANNER_RUNTIME_GUARD: ContextVar[PlannerRuntimeGuard | None] = ContextVar(
    "active_planner_runtime_guard",
    default=None,
)


@contextmanager
def activate_planner_runtime_guard() -> PlannerRuntimeGuard:
    guard = PlannerRuntimeGuard()
    token: Token[PlannerRuntimeGuard | None] = _ACTIVE_PLANNER_RUNTIME_GUARD.set(guard)
    try:
        yield guard
    finally:
        _ACTIVE_PLANNER_RUNTIME_GUARD.reset(token)


def get_active_planner_runtime_guard() -> PlannerRuntimeGuard | None:
    return _ACTIVE_PLANNER_RUNTIME_GUARD.get()


def build_guard_missing_info(guard: PlannerRuntimeGuard | None) -> list[str]:
    if guard is None:
        return []
    missing: list[str] = []
    seen: set[str] = set()
    for event in guard.events:
        if event.kind == "tool_budget_exhausted":
            key = "planner_tool_budget"
        elif event.tool in {"list", "fetch_keys"} and event.theme:
            key = f"state_path_missing:{event.theme}"
        elif event.theme:
            key = f"state_value_missing:{event.theme}"
        else:
            continue
        if key in seen:
            continue
        seen.add(key)
        missing.append(key)
    return missing


def _normalize_prefix(prefix: str | None) -> str:
    normalized = (prefix or "").strip()
    return normalized if normalized else "*"


def _normalize_theme(theme: str | None) -> str:
    normalized = " ".join((theme or "").strip().split())
    return normalized if normalized else "*"


def _merge_suggestions(
    groups: Sequence[Sequence[str] | Iterable[str]],
    *,
    limit: int = 5,
) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for candidate in group:
            if candidate in seen:
                continue
            seen.add(candidate)
            merged.append(candidate)
            if len(merged) >= limit:
                return merged
    return merged
