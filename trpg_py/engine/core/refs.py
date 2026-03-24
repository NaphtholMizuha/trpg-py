from __future__ import annotations

from typing import Any

from trpg_py.errors import ValidationError
from trpg_py.store import read


def collect_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        if "$ref" in value:
            ref = value["$ref"]
            if not isinstance(ref, str):
                raise ValidationError("Reference path must be a string")
            refs.append(ref)
        for nested in value.values():
            refs.extend(collect_refs(nested))
    elif isinstance(value, list):
        for nested in value:
            refs.extend(collect_refs(nested))
    return refs


def resolve_reference(path: str, state: dict[str, Any], context: dict[str, Any], results: dict[str, Any]) -> Any:
    namespace, _, remainder = path.partition(".")
    if namespace == "context":
        if not remainder:
            return context
        return read(context, remainder)
    if namespace == "state":
        if not remainder:
            return state
        return read(state, remainder)
    if namespace == "result":
        if not remainder:
            return results
        return read(results, remainder)
    raise ValidationError(f"Unsupported reference namespace in {path!r}")


def resolve_value(value: Any, state: dict[str, Any], context: dict[str, Any], results: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        if "$ref" in value:
            base = resolve_reference(value["$ref"], state, context, results)
            if "eq" in value:
                expected = resolve_value(value["eq"], state, context, results)
                return base == expected
            if "in" in value:
                options = resolve_value(value["in"], state, context, results)
                return base in options
            return base
        return {key: resolve_value(nested, state, context, results) for key, nested in value.items()}
    if isinstance(value, list):
        return [resolve_value(item, state, context, results) for item in value]
    return value
