from __future__ import annotations

from typing import Any

from trpg_py.errors import ExecutionError


def resolve_target_ids(args: dict[str, Any]) -> list[str]:
    targets = args.get("targets")
    if targets is None:
        return []
    if isinstance(targets, str):
        return [targets]
    if isinstance(targets, list):
        return [str(target) for target in targets]
    raise ExecutionError("targets must be a string or list of strings")


def format_template(template: str, **kwargs: Any) -> str:
    safe_values = {key: "" if value is None else value for key, value in kwargs.items()}
    return template.format(**safe_values)


def resolve_target_path(
    args: dict[str, Any],
    target_id: str,
    *,
    direct_key: str,
    template_key: str,
    default_template: str,
) -> str:
    direct = args.get(direct_key)
    if isinstance(direct, dict):
        if target_id not in direct:
            raise ExecutionError(f"{direct_key} mapping missing target {target_id!r}")
        return str(direct[target_id])
    if isinstance(direct, str):
        return direct
    template = str(args.get(template_key, default_template))
    return format_template(template, target_id=target_id)
