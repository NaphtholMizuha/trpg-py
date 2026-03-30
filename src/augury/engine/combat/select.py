from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from augury.engine.core.models import OperationResult, TaskStep
from augury.errors import ExecutionError, StatePathError, TargetingRangeError
from augury.store import read


DEFAULT_SELECT_FIELD_MAP = {
    "id": "id",
    "side": "side",
    "alive": "alive",
    "tags": "tags",
    "position.x": "position.x",
    "position.y": "position.y",
}


def run_select(step: TaskStep, args: dict[str, Any], state: dict[str, Any]) -> OperationResult:
    pool = args.get("entity_pool", state.get("actors", {}))
    actors = _normalize_actor_pool(pool)
    if step.kind == "target":
        source = args.get("source")
        if source is None:
            source = args.get("target_id")
        if source is None:
            raise ExecutionError("select.target requires source or target_id")
        if isinstance(source, list):
            target_ids = source
        else:
            target_ids = [source]
        _validate_select_targeting(step, args, actors, target_ids)
        return OperationResult(outputs={"target_ids": target_ids, "count": len(target_ids)})

    filtered = _apply_common_filters(actors, args)
    if step.kind == "filtered":
        return OperationResult(
            outputs={"target_ids": [_resolve_actor_id(actor, args) for actor in filtered], "count": len(filtered)}
        )

    if step.kind != "area":
        raise ExecutionError(f"Unsupported select kind: {step.kind}")

    origin = args.get("origin")
    if origin is None:
        raise ExecutionError("select.area requires origin")
    _validate_area_targeting(args, origin)
    shape = args.get("shape", "sphere")
    matched = []
    for actor in filtered:
        position = _resolve_actor_position(actor, args)
        if position is None:
            continue
        if _matches_shape(shape, origin, position, args):
            matched.append(_resolve_actor_id(actor, args))
    max_targets = args.get("max_targets")
    if max_targets is not None:
        matched = matched[: int(max_targets)]
    return OperationResult(outputs={"target_ids": matched, "count": len(matched), "shape": shape})


def _normalize_actor_pool(pool: Any) -> list[dict[str, Any]]:
    if isinstance(pool, dict):
        actors = []
        for actor_id, payload in pool.items():
            if not isinstance(payload, dict):
                continue
            actor = deepcopy(payload)
            actor.setdefault("id", actor_id)
            actors.append(actor)
        return actors
    if isinstance(pool, list):
        return [deepcopy(actor) for actor in pool if isinstance(actor, dict)]
    raise ExecutionError("entity_pool must be a dict or list")


def _apply_common_filters(actors: list[dict[str, Any]], args: dict[str, Any]) -> list[dict[str, Any]]:
    include_side_value = args.get("include_sides", args.get("include_side", []))
    if isinstance(include_side_value, str):
        include_sides = {include_side_value}
    else:
        include_sides = set(include_side_value)
    exclude_ids = set(args.get("exclude_ids", []))
    include_tags = set(args.get("include_tags", []))
    exclude_tags = set(args.get("exclude_tags", []))
    must_be_alive = bool(args.get("must_be_alive", False))
    filtered = []
    for actor in actors:
        actor_id = _resolve_actor_id(actor, args)
        if actor_id in exclude_ids:
            continue
        actor_side = _resolve_actor_field(actor, args, "side")
        if include_sides and actor_side not in include_sides:
            continue
        tags = set(_resolve_actor_field(actor, args, "tags", default=[]))
        if include_tags and not include_tags.issubset(tags):
            continue
        if exclude_tags and tags.intersection(exclude_tags):
            continue
        if must_be_alive and not bool(_resolve_actor_field(actor, args, "alive", default=False)):
            continue
        filtered.append(actor)
    return filtered


def _matches_shape(shape: str, origin: dict[str, Any], position: dict[str, Any], args: dict[str, Any]) -> bool:
    dx = position["x"] - origin["x"]
    dy = position["y"] - origin["y"]
    distance = math.dist((origin["x"], origin["y"]), (position["x"], position["y"]))
    if shape == "sphere":
        return distance <= float(args["radius"])
    if shape == "line":
        length = float(args["length"])
        width = float(args.get("width", 5))
        direction = args.get("direction", {"x": 1, "y": 0})
        vx, vy = float(direction["x"]), float(direction["y"])
        norm = math.hypot(vx, vy) or 1.0
        ux, uy = vx / norm, vy / norm
        projection = dx * ux + dy * uy
        perpendicular = abs(dx * uy - dy * ux)
        return 0 <= projection <= length and perpendicular <= width / 2
    if shape == "cone":
        length = float(args["length"])
        angle = float(args.get("angle", 90))
        direction = args.get("direction", {"x": 1, "y": 0})
        vx, vy = float(direction["x"]), float(direction["y"])
        norm = math.hypot(vx, vy) or 1.0
        target_norm = math.hypot(dx, dy) or 1.0
        dot = (dx * vx + dy * vy) / (norm * target_norm)
        dot = max(-1.0, min(1.0, dot))
        theta = math.degrees(math.acos(dot))
        return distance <= length and theta <= angle / 2
    if shape == "target":
        return distance == 0
    raise ExecutionError(f"Unsupported area shape: {shape}")


def _validate_select_targeting(
    step: TaskStep,
    args: dict[str, Any],
    actors: list[dict[str, Any]],
    target_ids: list[Any],
) -> None:
    targeting = args.get("targeting")
    if targeting is None:
        return
    source_position = _coerce_position(
        targeting.get("source_position"),
        context=f"{step.id} targeting.source_position",
    )
    max_range = float(targeting.get("max_range"))
    range_metric = str(targeting.get("range_metric"))
    actor_by_id = {_resolve_actor_id(actor, args): actor for actor in actors}
    for target_id in target_ids:
        actor = actor_by_id.get(str(target_id))
        if actor is None:
            raise ExecutionError(f"Target {target_id!r} was not found in entity_pool for range validation")
        target_position = _resolve_actor_position(actor, args)
        if target_position is None:
            raise ExecutionError(f"Target {target_id!r} is missing position fields required for range validation")
        distance = _measure_distance(source_position, target_position, range_metric)
        if distance > max_range:
            raise TargetingRangeError(
                f"Target {target_id!r} is out of range: distance={_format_number(distance)} > max_range={_format_number(max_range)}"
            )


def _validate_area_targeting(args: dict[str, Any], origin: Any) -> None:
    targeting = args.get("targeting")
    if targeting is None:
        return
    source_position = _coerce_position(
        targeting.get("source_position"),
        context="select.area targeting.source_position",
    )
    origin_position = _coerce_position(origin, context="select.area origin")
    max_range = float(targeting.get("max_range"))
    range_metric = str(targeting.get("range_metric"))
    distance = _measure_distance(source_position, origin_position, range_metric)
    if distance > max_range:
        raise TargetingRangeError(
            f"Area origin is out of range: distance={_format_number(distance)} > max_range={_format_number(max_range)}"
        )


def _coerce_position(value: Any, *, context: str) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ExecutionError(f"{context} must be an object with x and y")
    if "x" not in value or "y" not in value:
        raise ExecutionError(f"{context} must define both x and y")
    return {"x": float(value["x"]), "y": float(value["y"])}


def _measure_distance(
    source_position: dict[str, float],
    target_position: dict[str, float],
    range_metric: str,
) -> float:
    if range_metric == "euclidean":
        return math.dist(
            (source_position["x"], source_position["y"]),
            (target_position["x"], target_position["y"]),
        )
    raise ExecutionError(f"Unsupported range metric: {range_metric!r}")


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _resolve_actor_field(
    actor: dict[str, Any],
    args: dict[str, Any],
    logical_name: str,
    *,
    default: Any = None,
) -> Any:
    field_map = DEFAULT_SELECT_FIELD_MAP | dict(args.get("field_map", {}))
    path = field_map.get(logical_name)
    if path is None:
        return default
    try:
        return read(actor, path)
    except StatePathError:
        return default


def _resolve_actor_id(actor: dict[str, Any], args: dict[str, Any]) -> str:
    actor_id = _resolve_actor_field(actor, args, "id")
    if actor_id is None:
        raise ExecutionError("Actor entry is missing an id field for selection")
    return str(actor_id)


def _resolve_actor_position(actor: dict[str, Any], args: dict[str, Any]) -> dict[str, float] | None:
    x_value = _resolve_actor_field(actor, args, "position.x")
    y_value = _resolve_actor_field(actor, args, "position.y")
    if x_value is None or y_value is None:
        return None
    return {"x": float(x_value), "y": float(y_value)}
