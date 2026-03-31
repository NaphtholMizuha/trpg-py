from __future__ import annotations

from collections.abc import Callable
from difflib import SequenceMatcher
from typing import Any, Literal

from langchain_core.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field, model_validator

from augury.agent.planner_runtime_guards import get_active_planner_runtime_guard
from augury.store import keys as list_state_keys

DEFAULT_GREP_LIMIT = 5

_SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    ("armor_class", "armor", "ac"),
    ("hit_points", "hit_point", "health", "hp"),
    ("temporary_hit_points", "temp_hp", "temporary_hp"),
    ("temporary_armor_class_bonus", "temp_ac_bonus"),
    ("spell_slots", "spell_slot", "slots", "slot"),
    ("attack_bonus", "to_hit", "hit_bonus"),
    ("movement_speed", "move_speed", "speed"),
)

_SYNONYM_MAP: dict[str, set[str]] = {}
for group in _SYNONYM_GROUPS:
    normalized_group = {item.lower() for item in group}
    for item in normalized_group:
        _SYNONYM_MAP[item] = normalized_group


class GrepError(BaseModel):
    type: str
    message: str


class GrepMatch(BaseModel):
    path: str
    score: float = Field(ge=0.0)
    matched_terms: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)


class GrepResult(BaseModel):
    status: Literal["ok", "no_match", "error"]
    matches: list[GrepMatch] = Field(default_factory=list)
    error: GrepError | None = None


class GrepInput(BaseModel):
    query: str | None = Field(
        default=None,
        description="可选自由文本查询；适合直接提供短语或关键词串。",
    )
    terms: list[str] = Field(
        default_factory=list,
        description="可选关键词数组；工具会用这些词检索相关叶子路径。",
    )
    limit: int = Field(
        default=DEFAULT_GREP_LIMIT,
        ge=1,
        le=20,
        description="返回候选路径数量上限。",
    )

    @model_validator(mode="after")
    def validate_query_or_terms(self) -> "GrepInput":
        normalized_query = (self.query or "").strip()
        normalized_terms = [str(item).strip() for item in self.terms if str(item).strip()]
        if not normalized_query and not normalized_terms:
            raise ValueError("grep requires query or at least one term")
        self.query = normalized_query or None
        self.terms = normalized_terms
        return self


class GrepTool(BaseTool):
    name: str = "grep"
    description: str = (
        "根据关键词检索当前状态中最相关的叶子点路径候选。"
        "只做路径发现，不读取具体值，也不写状态。"
    )
    args_schema: type[BaseModel] = GrepInput

    state: Any = Field(exclude=True)
    state_provider: Callable[[], Any] | None = Field(default=None, exclude=True)

    def _run(
        self,
        query: str | None = None,
        terms: list[str] | None = None,
        limit: int = DEFAULT_GREP_LIMIT,
    ) -> dict[str, Any]:
        normalized_terms = _normalize_terms(query=query, terms=terms or [])
        _log_grep_input(query=query, terms=normalized_terms, limit=limit, tool_name=self.name)
        guard = get_active_planner_runtime_guard()
        grep_theme = _build_grep_theme(query=query, terms=normalized_terms)
        if guard is not None:
            guarded_result = guard.short_circuit_grep(tool_name=self.name, theme=grep_theme)
            if guarded_result is not None:
                logger.warning(
                    "tool_guard tool={} kind=repeated_theme theme={!r}",
                    self.name,
                    grep_theme,
                )
                validated = GrepResult.model_validate(guarded_result)
                _log_grep_output(validated, tool_name=self.name)
                return validated.model_dump(exclude_none=True)
        try:
            matches = grep_leaf_paths(self._resolve_state(), query=query, terms=normalized_terms, limit=limit)
            result = GrepResult(status="ok" if matches else "no_match", matches=matches)
        except Exception as exc:
            result = GrepResult(
                status="error",
                error=GrepError(type=exc.__class__.__name__, message=str(exc)),
            )
        _log_grep_output(result, tool_name=self.name)
        payload = result.model_dump(exclude_none=True)
        if guard is not None:
            guard.record_grep_result(theme=grep_theme, result=payload)
        return payload

    def _resolve_state(self) -> Any:
        if self.state_provider is not None:
            return self.state_provider()
        return self.state


def grep_leaf_paths(
    state: Any,
    *,
    query: str | None = None,
    terms: list[str] | None = None,
    limit: int = DEFAULT_GREP_LIMIT,
) -> list[GrepMatch]:
    normalized_terms = _normalize_terms(query=query, terms=terms or [])
    if not normalized_terms:
        return []

    candidates = list_state_keys(state)
    scored: list[tuple[float, int, str, list[str]]] = []
    for candidate in candidates:
        score, matched_terms = _score_candidate(candidate, normalized_terms)
        if score <= 0:
            continue
        scored.append((score, len(candidate), candidate, matched_terms))

    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    matches: list[GrepMatch] = []
    for score, _, path, matched_terms in scored[:limit]:
        matches.append(
            GrepMatch(
                path=path,
                score=round(score, 4),
                matched_terms=matched_terms,
                reason=_build_reason(path=path, matched_terms=matched_terms),
            )
        )
    return matches


def create_grep_tool(
    *,
    state: Any | None = None,
    state_provider: Callable[[], Any] | None = None,
) -> GrepTool:
    return GrepTool(state={} if state is None else state, state_provider=state_provider)


def _normalize_terms(*, query: str | None, terms: list[str]) -> list[str]:
    raw_terms: list[str] = []
    if query:
        raw_terms.extend(_split_query_terms(query))
    raw_terms.extend(term.strip().lower() for term in terms if term and term.strip())

    normalized: list[str] = []
    seen: set[str] = set()
    for term in raw_terms:
        canonical = term.replace("-", "_").replace(" ", "_")
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        normalized.append(canonical)
    return normalized


def _split_query_terms(query: str) -> list[str]:
    text = query.strip().lower()
    if not text:
        return []
    text = text.replace(".", " ").replace("/", " ")
    return [part for part in text.replace("-", " ").replace("_", " ").split() if len(part) >= 3]


def _score_candidate(candidate: str, terms: list[str]) -> tuple[float, list[str]]:
    candidate_lower = candidate.lower()
    segments = [segment for segment in candidate_lower.split(".") if segment]
    segment_text = " ".join(segments)
    matched_terms: list[str] = []
    score = 0.0

    for term in terms:
        term_variants = _expand_term_variants(term)
        term_score = 0.0
        matched = False
        for variant in term_variants:
            if variant in segments:
                term_score = max(term_score, 5.0)
                matched = True
                continue
            if len(variant) >= 3 and any(variant in segment for segment in segments):
                term_score = max(term_score, 3.0)
                matched = True
                continue
            seq_ratio = SequenceMatcher(a=variant, b=segment_text).ratio()
            if seq_ratio >= 0.72:
                term_score = max(term_score, 1.5 * seq_ratio)
                matched = True
        if matched:
            matched_terms.append(term)
            score += term_score

    if not matched_terms:
        return 0.0, []

    coverage = len(matched_terms) / max(len(terms), 1)
    leaf_bonus = 0.2 if "." in candidate_lower else 0.0
    score += coverage * 2.0 + leaf_bonus
    return score, matched_terms


def _expand_term_variants(term: str) -> set[str]:
    normalized = term.lower().replace("-", "_").replace(" ", "_")
    variants = {normalized}
    if normalized in _SYNONYM_MAP:
        variants.update(_SYNONYM_MAP[normalized])
    for synonym, group in _SYNONYM_MAP.items():
        if normalized in group:
            variants.update(group)
            variants.add(synonym)
    expanded: set[str] = set()
    for variant in variants:
        expanded.add(variant)
        expanded.update(part for part in variant.split("_") if part)
    return expanded


def _build_reason(*, path: str, matched_terms: list[str]) -> str:
    if matched_terms:
        return f"matched terms {', '.join(matched_terms)} in leaf path {path}"
    return f"matched leaf path {path}"


def _build_grep_theme(*, query: str | None, terms: list[str]) -> str | None:
    if terms:
        return " ".join(terms)
    normalized_query = (query or "").strip().lower()
    return normalized_query or None


def _log_grep_input(
    *,
    query: str | None,
    terms: list[str],
    limit: int,
    tool_name: str,
) -> None:
    logger.info(
        "tool_input tool={} query={!r} terms={} limit={}",
        tool_name,
        query,
        terms,
        limit,
    )


def _log_grep_output(result: GrepResult, *, tool_name: str) -> None:
    if result.status == "ok":
        logger.info(
            "tool_output tool={} status=ok matches={} sample_paths={}",
            tool_name,
            len(result.matches),
            [item.path for item in result.matches[:3]],
        )
        return
    if result.status == "no_match":
        logger.info(
            "tool_output tool={} status=no_match matches=0",
            tool_name,
        )
        return
    logger.error(
        "tool_output tool={} status=error error_type={} error_message={!r}",
        tool_name,
        result.error.type if result.error else "unknown",
        result.error.message if result.error else "",
    )
