from __future__ import annotations

from collections.abc import Iterable, Sequence
from difflib import SequenceMatcher


DEFAULT_SUGGESTION_LIMIT = 5


def suggest_paths(
    candidates: Sequence[str] | Iterable[str],
    query: str | None,
    *,
    limit: int = DEFAULT_SUGGESTION_LIMIT,
) -> list[str]:
    normalized_query = (query or "").strip()
    if not normalized_query:
        return []

    scored: list[tuple[float, int, str]] = []
    for candidate in _unique_candidates(candidates):
        score = _score_candidate(normalized_query, candidate)
        if score <= 0:
            continue
        scored.append((score, len(candidate), candidate))

    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [candidate for _, _, candidate in scored[:limit]]


def merge_suggestions(
    groups: Sequence[Sequence[str] | Iterable[str]],
    *,
    limit: int = DEFAULT_SUGGESTION_LIMIT,
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


def _unique_candidates(candidates: Sequence[str] | Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered


def _score_candidate(query: str, candidate: str) -> float:
    query_lower = query.lower()
    candidate_lower = candidate.lower()
    query_segments = _split_segments(query_lower)
    candidate_segments = _split_segments(candidate_lower)
    query_tokens = _split_tokens(query_lower)
    candidate_tokens = _split_tokens(candidate_lower)

    shared_prefix = _shared_prefix_segments(query_segments, candidate_segments)
    overlap = len(query_tokens & candidate_tokens)
    overlap_ratio = overlap / max(len(query_tokens), 1)
    seq_ratio = SequenceMatcher(a=query_lower, b=candidate_lower).ratio()
    contains_bonus = 0.0
    if query_lower in candidate_lower or candidate_lower in query_lower:
        contains_bonus = 0.5

    score = (shared_prefix * 3.0) + (overlap_ratio * 2.0) + seq_ratio + contains_bonus
    if shared_prefix == 0 and overlap == 0 and seq_ratio < 0.45:
        return 0.0
    return score


def _split_segments(value: str) -> list[str]:
    return [segment for segment in value.split(".") if segment]


def _split_tokens(value: str) -> set[str]:
    tokens: set[str] = set()
    for segment in _split_segments(value):
        for token in segment.replace("-", "_").split("_"):
            if token:
                tokens.add(token)
    return tokens


def _shared_prefix_segments(left: Sequence[str], right: Sequence[str]) -> int:
    count = 0
    for left_part, right_part in zip(left, right, strict=False):
        if left_part != right_part:
            break
        count += 1
    return count

