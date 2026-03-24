from __future__ import annotations

from copy import deepcopy
from typing import Any

from trpg_py.errors import StatePathError


def split_path(path: str) -> list[str | int]:
    if not path:
        raise StatePathError("State path cannot be empty")
    parts: list[str | int] = []
    for token in path.split("."):
        if token == "":
            raise StatePathError(f"Invalid empty token in path: {path!r}")
        parts.append(int(token) if token.isdigit() else token)
    return parts


def get_path(state: Any, path: str) -> Any:
    current = state
    for part in split_path(path):
        if isinstance(part, int):
            if isinstance(current, dict):
                str_part = str(part)
                if str_part in current:
                    current = current[str_part]
                    continue
            if not isinstance(current, list):
                raise StatePathError(f"Path {path!r} expected list before index {part}")
            if part < 0 or part >= len(current):
                raise StatePathError(f"Path {path!r} index {part} out of range")
            current = current[part]
        else:
            if not isinstance(current, dict):
                raise StatePathError(f"Path {path!r} expected dict before key {part!r}")
            if part not in current:
                raise StatePathError(f"Path {path!r} missing key {part!r}")
            current = current[part]
    return current


def has_path(state: Any, path: str) -> bool:
    try:
        get_path(state, path)
    except StatePathError:
        return False
    return True


def set_path(state: Any, path: str, value: Any) -> None:
    parts = split_path(path)
    current = state
    for index, part in enumerate(parts[:-1]):
        next_part = parts[index + 1]
        if isinstance(part, int):
            if isinstance(current, dict):
                str_part = str(part)
                if str_part not in current:
                    if isinstance(next_part, int):
                        raise StatePathError(
                            f"Path {path!r} cannot create missing list node for key {str_part!r}"
                        )
                    current[str_part] = {}
                current = current[str_part]
                continue
            if not isinstance(current, list):
                raise StatePathError(f"Path {path!r} expected list before index {part}")
            if part < 0 or part >= len(current):
                raise StatePathError(f"Path {path!r} index {part} out of range")
            current = current[part]
            continue

        if not isinstance(current, dict):
            raise StatePathError(f"Path {path!r} expected dict before key {part!r}")
        if part not in current:
            if isinstance(next_part, int):
                raise StatePathError(
                    f"Path {path!r} cannot create missing list node for key {part!r}"
                )
            current[part] = {}
        current = current[part]

    final = parts[-1]
    if isinstance(final, int):
        if isinstance(current, dict):
            current[str(final)] = deepcopy(value)
            return
        if not isinstance(current, list):
            raise StatePathError(f"Path {path!r} expected list before index {final}")
        if final < 0 or final >= len(current):
            raise StatePathError(f"Path {path!r} index {final} out of range")
        current[final] = deepcopy(value)
        return

    if not isinstance(current, dict):
        raise StatePathError(f"Path {path!r} expected dict before key {final!r}")
    current[final] = deepcopy(value)
