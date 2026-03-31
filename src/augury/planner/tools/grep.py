from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any, Literal

from langchain_core.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field, model_validator

from augury.store import keys as list_state_keys
from augury.store import read as read_state_path

DEFAULT_GREP_LIMIT = 100

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

_TOKEN_PATTERN = re.compile(r"\s*(\(|\)|&&|\|\||\"[^\"]+\"|'[^']+'|[^()\s&|]+)")


class GrepError(BaseModel):
    type: str
    message: str


class GrepResult(BaseModel):
    status: Literal["ok", "no_match", "error"]
    matches: list[str] = Field(default_factory=list)
    error: GrepError | None = None


class GrepInput(BaseModel):
    expressions: list[str] = Field(
        min_length=1,
        description="一个或多个布尔表达式字符串，例如 '(a && (b || c))'。",
    )
    limit: int = Field(
        default=DEFAULT_GREP_LIMIT,
        ge=1,
        le=1000,
        description="最终返回的命中行数量上限。",
    )

    @model_validator(mode="after")
    def normalize_expressions(self) -> "GrepInput":
        normalized = [str(item).strip() for item in self.expressions if str(item).strip()]
        if not normalized:
            raise ValueError("grep requires at least one expression")
        self.expressions = normalized
        return self


class GrepTool(BaseTool):
    name: str = "grep"
    description: str = (
        "将当前状态展平成 `a.b.c = data` 文本行，并基于布尔表达式数组返回所有命中的内容行。"
        "只读、无副作用，不写状态。"
    )
    args_schema: type[BaseModel] = GrepInput

    state: Any = Field(exclude=True)
    state_provider: Callable[[], Any] | None = Field(default=None, exclude=True)

    def _run(self, expressions: list[str], limit: int = DEFAULT_GREP_LIMIT) -> dict[str, Any]:
        normalized_input = GrepInput(expressions=expressions, limit=limit)
        _log_grep_input(normalized_input, tool_name=self.name)
        try:
            matches = grep_lines(
                self._resolve_state(),
                expressions=normalized_input.expressions,
                limit=normalized_input.limit,
            )
            result = GrepResult(status="ok" if matches else "no_match", matches=matches)
        except Exception as exc:
            result = GrepResult(
                status="error",
                error=GrepError(type=exc.__class__.__name__, message=str(exc)),
            )
        _log_grep_output(result, tool_name=self.name)
        return result.model_dump(exclude_none=True)

    def _resolve_state(self) -> Any:
        if self.state_provider is not None:
            return self.state_provider()
        return self.state


def grep_lines(
    state: Any,
    *,
    expressions: list[str],
    limit: int = DEFAULT_GREP_LIMIT,
) -> list[str]:
    normalized_input = GrepInput(expressions=expressions, limit=limit)
    predicates = [_compile_expression(expression) for expression in normalized_input.expressions]
    matches: list[str] = []
    for line in _flatten_state_lines(state):
        if any(predicate(line) for predicate in predicates):
            matches.append(line)
            if len(matches) >= normalized_input.limit:
                break
    return matches


def grep_leaf_paths(
    state: Any,
    *,
    expressions: list[str],
    limit: int = DEFAULT_GREP_LIMIT,
) -> list[str]:
    return grep_lines(state, expressions=expressions, limit=limit)


def create_grep_tool(
    *,
    state: Any | None = None,
    state_provider: Callable[[], Any] | None = None,
) -> GrepTool:
    return GrepTool(state={} if state is None else state, state_provider=state_provider)


def _flatten_state_lines(state: Any) -> list[str]:
    lines: list[str] = []
    for path in list_state_keys(state):
        value = read_state_path(state, path)
        lines.append(f"{path} = {_format_value(value)}")
    return lines


def _format_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None or isinstance(value, bool | int | float):
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _compile_expression(expression: str) -> Callable[[str], bool]:
    tokens = _tokenize_expression(expression)
    if not tokens:
        raise ValueError("grep expression must not be empty")
    parser = _ExpressionParser(tokens)
    predicate = parser.parse()
    if parser.has_remaining():
        raise ValueError(f"unexpected token {parser.peek()!r} in grep expression")
    return predicate


def _tokenize_expression(expression: str) -> list[str]:
    tokens: list[str] = []
    position = 0
    while position < len(expression):
        match = _TOKEN_PATTERN.match(expression, position)
        if match is None:
            raise ValueError(f"invalid grep expression near {expression[position:]!r}")
        token = match.group(1)
        position = match.end()
        if token.strip():
            tokens.append(token)
    return tokens


class _ExpressionParser:
    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.index = 0

    def parse(self) -> Callable[[str], bool]:
        return self._parse_or()

    def has_remaining(self) -> bool:
        return self.index < len(self.tokens)

    def peek(self) -> str | None:
        if self.index >= len(self.tokens):
            return None
        return self.tokens[self.index]

    def _parse_or(self) -> Callable[[str], bool]:
        left = self._parse_and()
        while self.peek() == "||":
            self.index += 1
            right = self._parse_and()
            previous = left
            left = lambda line, left=previous, right=right: left(line) or right(line)
        return left

    def _parse_and(self) -> Callable[[str], bool]:
        left = self._parse_primary()
        while self.peek() == "&&":
            self.index += 1
            right = self._parse_primary()
            previous = left
            left = lambda line, left=previous, right=right: left(line) and right(line)
        return left

    def _parse_primary(self) -> Callable[[str], bool]:
        token = self.peek()
        if token is None:
            raise ValueError("unexpected end of grep expression")
        if token == "(":
            self.index += 1
            inner = self._parse_or()
            if self.peek() != ")":
                raise ValueError("grep expression is missing a closing ')'")
            self.index += 1
            return inner
        if token in {"&&", "||", ")"}:
            raise ValueError(f"unexpected token {token!r} in grep expression")
        self.index += 1
        term = _normalize_atom(token)
        return lambda line, term=term: _line_matches_term(line, term)


def _normalize_atom(token: str) -> str:
    stripped = token.strip()
    if (stripped.startswith('"') and stripped.endswith('"')) or (
        stripped.startswith("'") and stripped.endswith("'")
    ):
        stripped = stripped[1:-1]
    return stripped.lower().replace("-", "_").replace(" ", "_")


def _line_matches_term(line: str, term: str) -> bool:
    line_lower = line.lower()
    line_tokens = set(_split_line_tokens(line_lower))
    for variant in _expand_term_variants(term):
        normalized_variant = variant.lower().replace("-", "_").replace(" ", "_")
        if normalized_variant in line_tokens:
            return True
        if len(normalized_variant) >= 3 and normalized_variant in line_lower:
            return True
        split_variant = [part for part in normalized_variant.split("_") if part]
        if split_variant and all(part in line_tokens for part in split_variant):
            return True
    return False


def _split_line_tokens(value: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9_]+", value.replace("-", "_")) if token]


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


def _log_grep_input(input_payload: GrepInput, *, tool_name: str) -> None:
    logger.info(
        "tool_input tool={} expressions={} limit={} expression_preview={}",
        tool_name,
        len(input_payload.expressions),
        input_payload.limit,
        input_payload.expressions[:2],
    )


def _log_grep_output(result: GrepResult, *, tool_name: str) -> None:
    if result.status == "ok":
        logger.info(
            "tool_output tool={} status=ok matches={} sample_matches={}",
            tool_name,
            len(result.matches),
            result.matches[:3],
        )
        return
    if result.status == "no_match":
        logger.info("tool_output tool={} status=no_match matches=0", tool_name)
        return
    logger.error(
        "tool_output tool={} status=error error_type={} error_message={!r}",
        tool_name,
        result.error.type if result.error else "unknown",
        result.error.message if result.error else "",
    )
