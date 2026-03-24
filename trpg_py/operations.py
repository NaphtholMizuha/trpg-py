from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from trpg_py.dice import DiceRoller, parse_dice_spec
from trpg_py.errors import ExecutionError, ValidationError
from trpg_py.models import ChangeInstruction, OperationResult, TaskDocument, TaskStep
from trpg_py.state import get_path, has_path


SUPPORTED_TYPES = {"select", "check", "damage", "heal", "resource", "effect", "state"}
SUPPORTED_KINDS = {
    "select": {"target", "area", "filtered"},
    "check": {"attack", "save", "ability", "skill"},
    "damage": {"apply"},
    "heal": {"apply"},
    "resource": {"consume"},
    "effect": {"add", "remove"},
    "state": {"set", "adjust"},
}
SUPPORTED_CHECK_TAGS = {"nat", "adv", "disadv"}
DEFAULT_SELECT_FIELD_MAP = {
    "id": "id",
    "side": "side",
    "alive": "alive",
    "tags": "tags",
    "position.x": "position.x",
    "position.y": "position.y",
}


def dispatch_step(
    step: TaskStep,
    resolved_args: dict[str, Any],
    state: dict[str, Any],
    task: TaskDocument,
    results: dict[str, Any],
    roller: DiceRoller,
) -> OperationResult:
    if step.type == "select":
        return _run_select(step, resolved_args, state)
    if step.type == "check":
        return _run_check(step, resolved_args, state, results, roller)
    if step.type == "damage":
        return _run_damage(step, resolved_args, state, results, roller)
    if step.type == "heal":
        return _run_heal(resolved_args, state, roller)
    if step.type == "resource":
        return _run_resource(resolved_args, state)
    if step.type == "effect":
        return _run_effect(step, resolved_args, state)
    if step.type == "state":
        return _run_state(resolved_args, state, step.kind)
    raise ValidationError(f"Unsupported step type: {step.type}")


def _run_select(step: TaskStep, args: dict[str, Any], state: dict[str, Any]) -> OperationResult:
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
        return OperationResult(
            outputs={
                "target_ids": target_ids,
                "count": len(target_ids),
            }
        )

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
    return OperationResult(
        outputs={
            "target_ids": matched,
            "count": len(matched),
            "shape": shape,
        }
    )


def _run_check(
    step: TaskStep,
    args: dict[str, Any],
    state: dict[str, Any],
    results: dict[str, Any],
    roller: DiceRoller,
) -> OperationResult:
    dice = args.get("dice")
    if not isinstance(dice, str):
        raise ExecutionError("check step requires a dice string")
    parse_dice_spec(dice)
    target_ids = _resolve_target_ids(args)
    if not target_ids and args.get("target_id") is not None:
        target_ids = [str(args["target_id"])]
    if step.kind == "attack" and len(target_ids) > 1:
        raise ExecutionError("check.attack currently supports a single target")
    if step.kind == "attack" and not target_ids:
        target_ids = [args.get("target_id") or "target"]
    if step.kind in {"save", "ability", "skill"} and not target_ids:
        target_ids = [args.get("target_id") or "self"]

    target_results: dict[str, Any] = {}
    for target_id in target_ids:
        target_results[target_id] = _run_single_check(step, args, state, target_id, roller)

    outputs: dict[str, Any] = {
        "target_ids": target_ids,
        "target_results": target_results,
    }
    if len(target_ids) == 1:
        outputs.update(target_results[target_ids[0]])
        outputs["target_id"] = target_ids[0]
    return OperationResult(outputs=outputs)


def _run_single_check(
    step: TaskStep,
    args: dict[str, Any],
    state: dict[str, Any],
    target_id: str,
    roller: DiceRoller,
) -> dict[str, Any]:
    dice = args["dice"]
    tags = set(args.get("tags", step.tags))
    mode = _resolve_roll_mode(tags)
    raw_rolls: list[list[int]]
    if mode == "normal":
        raw_rolls = [roller.roll(dice)]
    else:
        raw_rolls = [roller.roll(dice), roller.roll(dice)]

    totals = [sum(group) for group in raw_rolls]
    if mode == "advantage":
        chosen_index = 0 if totals[0] >= totals[1] else 1
    elif mode == "disadvantage":
        chosen_index = 0 if totals[0] <= totals[1] else 1
    else:
        chosen_index = 0

    chosen_roll = raw_rolls[chosen_index]
    chosen_total = totals[chosen_index]
    natural = chosen_roll[0]
    modifier = _resolve_check_modifier(step.kind, args, state, target_id)
    total = chosen_total + modifier
    threshold = _resolve_threshold(step.kind, args, state, target_id)
    outcome = "success" if total >= threshold else "fail"
    auto_hit = False
    auto_miss = False
    critical = False
    if "nat" in tags and step.kind == "attack":
        if natural == 20:
            outcome = "crit_success"
            auto_hit = True
            critical = True
        elif natural == 1:
            outcome = "crit_fail"
            auto_miss = True

    return {
        "rolls": [group[0] if len(group) == 1 else sum(group) for group in raw_rolls],
        "raw_rolls": raw_rolls,
        "natural": natural,
        "chosen": chosen_total,
        "modifier": modifier,
        "total": total,
        "threshold": threshold,
        "roll_mode": mode,
        "outcome": outcome,
        "success": outcome in {"success", "crit_success"},
        "critical": critical,
        "auto_hit": auto_hit,
        "auto_miss": auto_miss,
    }


def _run_damage(
    step: TaskStep,
    args: dict[str, Any],
    state: dict[str, Any],
    results: dict[str, Any],
    roller: DiceRoller,
) -> OperationResult:
    target_ids = _resolve_target_ids(args)
    if not target_ids:
        raise ExecutionError("damage.apply requires targets")
    components = args.get("damage")
    if isinstance(components, dict):
        components = [components]
    if not isinstance(components, list) or not components:
        raise ExecutionError("damage.apply requires damage components")
    is_critical = bool(args.get("is_critical", False))
    save_result = args.get("save_result")
    on_save = args.get("on_save")
    per_target_roll = bool(args.get("per_target_roll", False))
    component_rolls = None if per_target_roll else _roll_damage_components(components, roller, is_critical)

    changes: list[ChangeInstruction] = []
    per_target: dict[str, Any] = {}
    for target_id in target_ids:
        if per_target_roll or component_rolls is None:
            rolled = _roll_damage_components(components, roller, is_critical)
        else:
            rolled = deepcopy(component_rolls)
        base_total = sum(item["total"] for item in rolled)
        multiplier = 1.0
        if save_result and isinstance(save_result, dict):
            save_entry = save_result.get("target_results", {}).get(target_id)
            if save_entry and save_entry.get("success"):
                if on_save == "half":
                    multiplier = 0.5
                elif on_save == "none":
                    multiplier = 0.0
        final_total = math.floor(base_total * multiplier)
        hp_path = _resolve_target_path(
            args,
            target_id,
            direct_key="target_hp_path",
            template_key="target_hp_path_template",
            default_template="actors.{target_id}.hp.current",
        )
        current_hp = int(get_path(state, hp_path))
        changes.append(ChangeInstruction(path=hp_path, value=max(0, current_hp - final_total)))
        per_target[target_id] = {
            "components": rolled,
            "base_total": base_total,
            "multiplier": multiplier,
            "final_total": final_total,
        }
    return OperationResult(
        outputs={
            "target_ids": target_ids,
            "is_critical": is_critical,
            "per_target": per_target,
        }
    , changes=changes)


def _run_heal(args: dict[str, Any], state: dict[str, Any], roller: DiceRoller) -> OperationResult:
    target_ids = _resolve_target_ids(args)
    if not target_ids:
        raise ExecutionError("heal.apply requires targets")
    amount = args.get("amount")
    if amount is None:
        components = args.get("healing")
        if isinstance(components, dict):
            components = [components]
        if not isinstance(components, list) or not components:
            raise ExecutionError("heal.apply requires amount or healing components")
        amount = sum(item["total"] for item in _roll_damage_components(components, roller, False))
    changes: list[ChangeInstruction] = []
    per_target: dict[str, Any] = {}
    for target_id in target_ids:
        hp_path = _resolve_target_path(
            args,
            target_id,
            direct_key="target_hp_path",
            template_key="target_hp_path_template",
            default_template="actors.{target_id}.hp.current",
        )
        current_hp = int(get_path(state, hp_path))
        requested_total = int(amount)
        new_hp = current_hp + requested_total
        max_hp = _resolve_target_max_hp(args, state, target_id, hp_path)
        capped = False
        if max_hp is not None:
            capped = new_hp > max_hp
            new_hp = min(new_hp, max_hp)
        changes.append(ChangeInstruction(path=hp_path, value=new_hp))
        per_target[target_id] = {
            "requested_total": requested_total,
            "final_total": max(0, new_hp - current_hp),
            "max_hp": max_hp,
            "capped": capped,
        }
    return OperationResult(outputs={"target_ids": target_ids, "per_target": per_target}, changes=changes)


def _run_resource(args: dict[str, Any], state: dict[str, Any]) -> OperationResult:
    path = args.get("path")
    if not isinstance(path, str):
        raise ExecutionError("resource.consume requires a path")
    cost = int(args.get("cost", 1))
    current = int(get_path(state, path))
    if current < cost:
        raise ExecutionError(f"Insufficient resource at {path!r}: {current} < {cost}")
    return OperationResult(
        outputs={"path": path, "cost": cost, "remaining": current - cost},
        changes=[ChangeInstruction(path=path, value=current - cost)],
    )


def _run_effect(step: TaskStep, args: dict[str, Any], state: dict[str, Any]) -> OperationResult:
    target_ids = _resolve_target_ids(args)
    if not target_ids:
        raise ExecutionError("effect step requires targets")
    changes: list[ChangeInstruction] = []
    outputs: dict[str, Any] = {"target_ids": target_ids}
    if step.kind == "add":
        effect = args.get("effect")
        if not isinstance(effect, dict):
            raise ExecutionError("effect.add requires an effect object")
        for target_id in target_ids:
            path = _resolve_target_path(
                args,
                target_id,
                direct_key="effects_path",
                template_key="effects_path_template",
                default_template="actors.{target_id}.effects",
            )
            current = deepcopy(get_path(state, path)) if has_path(state, path) else []
            if not isinstance(current, list):
                raise ExecutionError(f"Effect path {path!r} is not a list")
            current.append(deepcopy(effect))
            changes.append(ChangeInstruction(path=path, value=current))
        outputs["effect"] = effect
        return OperationResult(outputs=outputs, changes=changes)

    if step.kind == "remove":
        effect_id = args.get("effect_id")
        if effect_id is None:
            raise ExecutionError("effect.remove requires effect_id")
        removed = []
        for target_id in target_ids:
            path = _resolve_target_path(
                args,
                target_id,
                direct_key="effects_path",
                template_key="effects_path_template",
                default_template="actors.{target_id}.effects",
            )
            current = deepcopy(get_path(state, path)) if has_path(state, path) else []
            if not isinstance(current, list):
                raise ExecutionError(f"Effect path {path!r} is not a list")
            next_effects = [item for item in current if item.get("id") != effect_id]
            removed.append(len(current) - len(next_effects))
            changes.append(ChangeInstruction(path=path, value=next_effects))
        outputs["effect_id"] = effect_id
        outputs["removed_counts"] = removed
        return OperationResult(outputs=outputs, changes=changes)

    raise ExecutionError(f"Unsupported effect kind: {step.kind}")


def _run_state(args: dict[str, Any], state: dict[str, Any], kind: str) -> OperationResult:
    path = args.get("path")
    if not isinstance(path, str):
        raise ExecutionError("state step requires path")
    if kind == "set":
        return OperationResult(outputs={"path": path, "value": args.get("value")}, changes=[ChangeInstruction(path=path, value=args.get("value"))])
    if kind == "adjust":
        delta = int(args.get("delta", 0))
        current = int(get_path(state, path))
        return OperationResult(outputs={"path": path, "delta": delta}, changes=[ChangeInstruction(path=path, value=current + delta)])
    raise ExecutionError(f"Unsupported state kind: {kind}")


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


def _resolve_target_ids(args: dict[str, Any]) -> list[str]:
    targets = args.get("targets")
    if targets is None:
        return []
    if isinstance(targets, str):
        return [targets]
    if isinstance(targets, list):
        return [str(target) for target in targets]
    raise ExecutionError("targets must be a string or list of strings")


def _resolve_roll_mode(tags: set[str]) -> str:
    if "adv" in tags and "disadv" in tags:
        return "normal"
    if "adv" in tags:
        return "advantage"
    if "disadv" in tags:
        return "disadvantage"
    return "normal"


def _resolve_check_modifier(kind: str, args: dict[str, Any], state: dict[str, Any], target_id: str) -> int:
    if "modifier" in args:
        modifier = args["modifier"]
        if isinstance(modifier, dict):
            if target_id in modifier:
                return int(modifier[target_id])
            raise ExecutionError(f"Modifier mapping missing target {target_id!r}")
        return int(modifier)
    if "modifier_path" in args:
        return int(get_path(state, str(args["modifier_path"])))
    if "modifier_path_template" in args:
        path = _format_template(
            str(args["modifier_path_template"]),
            target_id=target_id,
            ability=args.get("ability"),
            skill=args.get("skill"),
            kind=kind,
        )
        return int(get_path(state, path))
    actor = state.get("actors", {}).get(target_id, {})
    ability = args.get("ability")
    if kind == "save" and ability:
        return int(actor.get("saves", {}).get(ability, 0))
    if kind == "ability" and ability:
        ability_payload = actor.get("abilities", {}).get(ability, 0)
        if isinstance(ability_payload, dict):
            return int(ability_payload.get("modifier", 0))
        return int(ability_payload)
    if kind == "skill":
        skill = args.get("skill")
        return int(actor.get("skills", {}).get(skill, 0))
    return 0


def _resolve_threshold(kind: str, args: dict[str, Any], state: dict[str, Any], target_id: str) -> int:
    if kind == "attack":
        if "target_ac" in args:
            return int(args["target_ac"])
        if "target_ac_path" in args:
            return int(get_path(state, str(args["target_ac_path"])))
        if "target_ac_path_template" in args:
            path = _format_template(str(args["target_ac_path_template"]), target_id=target_id, kind=kind)
            return int(get_path(state, path))
        actor = state.get("actors", {}).get(target_id, {})
        if "ac" not in actor:
            raise ExecutionError("attack check requires target_ac or target actor ac")
        return int(actor["ac"])
    if "dc_path" in args:
        return int(get_path(state, str(args["dc_path"])))
    if "dc" not in args:
        raise ExecutionError(f"{kind} check requires dc")
    return int(args["dc"])


def _roll_damage_components(
    components: list[dict[str, Any]],
    roller: DiceRoller,
    is_critical: bool,
) -> list[dict[str, Any]]:
    rolled_components = []
    for component in components:
        dice = component.get("dice")
        bonus = int(component.get("bonus", 0))
        rolls: list[int] = []
        if dice:
            parse_dice_spec(dice)
            rolls.extend(roller.roll(dice))
            if is_critical:
                rolls.extend(roller.roll(dice))
        rolled_components.append(
            {
                "dice": dice,
                "rolls": rolls,
                "bonus": bonus,
                "damage_type": component.get("damage_type"),
                "total": sum(rolls) + bonus,
            }
        )
    return rolled_components


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
        return get_path(actor, path)
    except Exception:
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


def _format_template(template: str, **kwargs: Any) -> str:
    safe_values = {key: "" if value is None else value for key, value in kwargs.items()}
    return template.format(**safe_values)


def _resolve_target_path(
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
    return _format_template(template, target_id=target_id)


def _resolve_target_max_hp(
    args: dict[str, Any],
    state: dict[str, Any],
    target_id: str,
    hp_path: str,
) -> int | None:
    if "target_hp_max_path" in args or "target_hp_max_path_template" in args:
        path = _resolve_target_path(
            args,
            target_id,
            direct_key="target_hp_max_path",
            template_key="target_hp_max_path_template",
            default_template="",
        )
        return int(get_path(state, path))
    inferred_path = _infer_default_max_hp_path(hp_path)
    if inferred_path and has_path(state, inferred_path):
        return int(get_path(state, inferred_path))
    return None


def _infer_default_max_hp_path(hp_path: str) -> str | None:
    suffix = ".current"
    if not hp_path.endswith(suffix):
        return None
    return hp_path[: -len(suffix)] + ".max"
