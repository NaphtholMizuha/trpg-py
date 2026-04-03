from __future__ import annotations

import json
from typing import Any

from augury import FixedDiceRoller
from augury.store import keys as list_state_keys
from augury.store import read as read_state_path


def format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def build_smoke_roller() -> FixedDiceRoller:
    return FixedDiceRoller([4] * 128)


def summarize_state_changes(
    initial_state: dict[str, Any],
    final_state: dict[str, Any],
) -> list[dict[str, Any]]:
    paths = sorted(set(list_state_keys(initial_state)) | set(list_state_keys(final_state)))
    changes: list[dict[str, Any]] = []
    for path in paths:
        before = _read_if_present(initial_state, path)
        after = _read_if_present(final_state, path)
        if before == after:
            continue
        changes.append(
            {
                "path": path,
                "old_value": before,
                "new_value": after,
            }
        )
    return changes


def render_change_lines(changes: list[dict[str, Any]]) -> list[str]:
    if not changes:
        return ["- (none)"]
    return [
        "- " + f"{change['path']}: {format_value(change['old_value'])} -> {format_value(change['new_value'])}"
        for change in changes
    ]


def _read_if_present(state: dict[str, Any], path: str) -> Any:
    try:
        return read_state_path(state, path)
    except Exception:
        return None


__all__ = [
    "build_smoke_roller",
    "format_value",
    "render_change_lines",
    "summarize_state_changes",
]
