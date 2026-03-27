from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel


_MAX_TEXT_LENGTH = 2000
_MAX_LIST_ITEMS = 20
_MAX_DICT_ITEMS = 20


def resolve_project_root(config_path: str | None) -> Path:
    if config_path is None:
        return Path.cwd().resolve()
    resolved = Path(config_path).expanduser().resolve()
    if resolved.parent.name == "config":
        return resolved.parent.parent
    return resolved.parent


def build_planner_log_path(project_root: Path, run_id: str, *, now: datetime | None = None) -> Path:
    timestamp = now or datetime.now()
    date_dir = timestamp.strftime("%Y-%m-%d")
    file_name = f"{timestamp.strftime('%Y%m%d-%H%M%S')}-{run_id}.log"
    return project_root / "logs" / "planner" / date_dir / file_name


def serialize_for_log(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return serialize_for_log(value.model_dump(exclude_none=True))
    if isinstance(value, dict):
        return {
            str(key): serialize_for_log(item)
            for key, item in list(value.items())[:_MAX_DICT_ITEMS]
        }
    if isinstance(value, list | tuple):
        return [serialize_for_log(item) for item in list(value)[:_MAX_LIST_ITEMS]]
    if isinstance(value, str):
        if len(value) <= _MAX_TEXT_LENGTH:
            return value
        return value[: _MAX_TEXT_LENGTH - 12] + "...<truncated>"
    if value is None or isinstance(value, bool | int | float):
        return value
    return repr(value)


def summarize_ai_message(message: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in (
        "content",
        "tool_calls",
        "invalid_tool_calls",
        "response_metadata",
        "usage_metadata",
        "additional_kwargs",
    ):
        if not hasattr(message, key):
            continue
        value = getattr(message, key)
        if value in (None, "", [], {}, ()):
            continue
        summary[key] = serialize_for_log(value)
    if not summary:
        summary["repr"] = repr(message)
    return summary
