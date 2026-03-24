from __future__ import annotations

from copy import deepcopy
from typing import Any
from collections.abc import Callable
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


def _read_one(state: Any, path: str) -> Any:
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
            continue
        if not isinstance(current, dict):
            raise StatePathError(f"Path {path!r} expected dict before key {part!r}")
        if part not in current:
            raise StatePathError(f"Path {path!r} missing key {part!r}")
        current = current[part]
    return current


def _write_one(state: Any, path: str, value: Any) -> Any:
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
    written = deepcopy(value)
    if isinstance(final, int):
        if isinstance(current, dict):
            current[str(final)] = written
            return written
        if not isinstance(current, list):
            raise StatePathError(f"Path {path!r} expected list before index {final}")
        if final < 0 or final >= len(current):
            raise StatePathError(f"Path {path!r} index {final} out of range")
        current[final] = written
        return written
    if not isinstance(current, dict):
        raise StatePathError(f"Path {path!r} expected dict before key {final!r}")
    current[final] = written
    return written


def read(state: Any, path: str) -> Any:
    return _read_one(state, path)


def reads(state: Any, paths: list[str]) -> list[Any]:
    return [_read_one(state, path) for path in paths]


def write(state: Any, path: str, value: Any) -> Any:
    return _write_one(state, path, value)


def writes(state: Any, items: list[tuple[str, Any] | dict[str, Any]]) -> list[Any]:
    results: list[Any] = []
    for item in items:
        if isinstance(item, dict):
            path = str(item["path"])
            value = item.get("value")
        else:
            path, value = item
        results.append(_write_one(state, path, value))
    return results


def mod(state: Any, path: str, fn: Callable[[Any], Any]) -> Any:
    current = _read_one(state, path)
    next_value = fn(current)
    return _write_one(state, path, next_value)


def mods(
    state: Any,
    items: list[tuple[str, Callable[[Any], Any]] | dict[str, Any]],
) -> list[Any]:
    results: list[Any] = []
    for item in items:
        if isinstance(item, dict):
            path = str(item["path"])
            fn = item["fn"]
        else:
            path, fn = item
        results.append(mod(state, path, fn))
    return results


__all__ = ["mod", "mods", "read", "reads", "split_path", "write", "writes"]
