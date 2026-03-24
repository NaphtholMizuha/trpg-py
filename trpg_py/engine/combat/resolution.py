from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from trpg_py.engine.combat.common import resolve_target_ids, resolve_target_path
from trpg_py.engine.core.dice import DiceRoller, parse_dice_spec
from trpg_py.engine.core.models import ChangeInstruction, OperationResult, TaskStep
from trpg_py.errors import ExecutionError
from trpg_py.store import read
from trpg_py.store.compat import has_path


def run_damage(
    step: TaskStep,
    args: dict[str, Any],
    state: dict[str, Any],
    results: dict[str, Any],
    roller: DiceRoller,
) -> OperationResult:
    target_ids = resolve_target_ids(args)
    if not target_ids and "targets" in args:
        return OperationResult(outputs={"target_ids": [], "is_critical": bool(args.get("is_critical", False)), "per_target": {}})
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
        hp_path = resolve_target_path(
            args,
            target_id,
            direct_key="target_hp_path",
            template_key="target_hp_path_template",
            default_template="actors.{target_id}.hp.current",
        )
        current_hp = int(read(state, hp_path))
        changes.append(ChangeInstruction(path=hp_path, value=max(0, current_hp - final_total)))
        per_target[target_id] = {
            "components": rolled,
            "base_total": base_total,
            "multiplier": multiplier,
            "final_total": final_total,
        }
    return OperationResult(outputs={"target_ids": target_ids, "is_critical": is_critical, "per_target": per_target}, changes=changes)


def run_heal(args: dict[str, Any], state: dict[str, Any], roller: DiceRoller) -> OperationResult:
    target_ids = resolve_target_ids(args)
    if not target_ids and "targets" in args:
        return OperationResult(outputs={"target_ids": [], "per_target": {}}, changes=[])
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
        hp_path = resolve_target_path(
            args,
            target_id,
            direct_key="target_hp_path",
            template_key="target_hp_path_template",
            default_template="actors.{target_id}.hp.current",
        )
        current_hp = int(read(state, hp_path))
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


def run_resource(args: dict[str, Any], state: dict[str, Any]) -> OperationResult:
    path = args.get("path")
    if not isinstance(path, str):
        raise ExecutionError("resource.consume requires a path")
    cost = int(args.get("cost", 1))
    current = int(read(state, path))
    if current < cost:
        raise ExecutionError(f"Insufficient resource at {path!r}: {current} < {cost}")
    return OperationResult(
        outputs={"path": path, "cost": cost, "remaining": current - cost},
        changes=[ChangeInstruction(path=path, value=current - cost)],
    )


def run_effect(step: TaskStep, args: dict[str, Any], state: dict[str, Any]) -> OperationResult:
    target_ids = resolve_target_ids(args)
    if not target_ids and "targets" in args:
        return OperationResult(outputs={"target_ids": []}, changes=[])
    if not target_ids:
        raise ExecutionError("effect step requires targets")
    changes: list[ChangeInstruction] = []
    outputs: dict[str, Any] = {"target_ids": target_ids}
    if step.kind == "add":
        effect = args.get("effect")
        if not isinstance(effect, dict):
            raise ExecutionError("effect.add requires an effect object")
        for target_id in target_ids:
            path = resolve_target_path(
                args,
                target_id,
                direct_key="effects_path",
                template_key="effects_path_template",
                default_template="actors.{target_id}.effects",
            )
            current = deepcopy(read(state, path)) if has_path(state, path) else []
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
            path = resolve_target_path(
                args,
                target_id,
                direct_key="effects_path",
                template_key="effects_path_template",
                default_template="actors.{target_id}.effects",
            )
            current = deepcopy(read(state, path)) if has_path(state, path) else []
            if not isinstance(current, list):
                raise ExecutionError(f"Effect path {path!r} is not a list")
            next_effects = [item for item in current if item.get("id") != effect_id]
            removed.append(len(current) - len(next_effects))
            changes.append(ChangeInstruction(path=path, value=next_effects))
        outputs["effect_id"] = effect_id
        outputs["removed_counts"] = removed
        return OperationResult(outputs=outputs, changes=changes)

    raise ExecutionError(f"Unsupported effect kind: {step.kind}")


def run_state(args: dict[str, Any], state: dict[str, Any], kind: str) -> OperationResult:
    path = args.get("path")
    if not isinstance(path, str):
        raise ExecutionError("state step requires path")
    if kind == "set":
        return OperationResult(
            outputs={"path": path, "value": args.get("value")},
            changes=[ChangeInstruction(path=path, value=args.get("value"))],
        )
    if kind == "adjust":
        delta = int(args.get("delta", 0))
        current = int(read(state, path))
        return OperationResult(
            outputs={"path": path, "delta": delta},
            changes=[ChangeInstruction(path=path, value=current + delta)],
        )
    raise ExecutionError(f"Unsupported state kind: {kind}")


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


def _resolve_target_max_hp(
    args: dict[str, Any],
    state: dict[str, Any],
    target_id: str,
    hp_path: str,
) -> int | None:
    if "target_hp_max_path" in args or "target_hp_max_path_template" in args:
        path = resolve_target_path(
            args,
            target_id,
            direct_key="target_hp_max_path",
            template_key="target_hp_max_path_template",
            default_template="",
        )
        return int(read(state, path))
    inferred_path = _infer_default_max_hp_path(hp_path)
    if inferred_path and has_path(state, inferred_path):
        return int(read(state, inferred_path))
    return None


def _infer_default_max_hp_path(hp_path: str) -> str | None:
    suffix = ".current"
    if not hp_path.endswith(suffix):
        return None
    return hp_path[: -len(suffix)] + ".max"
