from __future__ import annotations

from typing import Any

from trpg_py.engine.combat.common import format_template, resolve_target_ids
from trpg_py.engine.core.dice import DiceRoller, parse_dice_spec
from trpg_py.engine.core.models import OperationResult, TaskStep
from trpg_py.errors import ExecutionError
from trpg_py.store import read


SUPPORTED_CHECK_TAGS = {"nat", "adv", "disadv"}


def run_check(
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
    explicit_targets = "targets" in args
    target_ids = resolve_target_ids(args)
    if explicit_targets and not target_ids:
        return OperationResult(outputs={"target_ids": [], "target_results": {}})
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

    outputs: dict[str, Any] = {"target_ids": target_ids, "target_results": target_results}
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
        return int(read(state, str(args["modifier_path"])))
    if "modifier_path_template" in args:
        path = format_template(
            str(args["modifier_path_template"]),
            target_id=target_id,
            ability=args.get("ability"),
            skill=args.get("skill"),
            kind=kind,
        )
        return int(read(state, path))
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
            return int(read(state, str(args["target_ac_path"])))
        if "target_ac_path_template" in args:
            path = format_template(str(args["target_ac_path_template"]), target_id=target_id, kind=kind)
            return int(read(state, path))
        actor = state.get("actors", {}).get(target_id, {})
        if "ac" not in actor:
            raise ExecutionError("attack check requires target_ac or target actor ac")
        return int(actor["ac"])
    if "dc_path" in args:
        return int(read(state, str(args["dc_path"])))
    if "dc" not in args:
        raise ExecutionError(f"{kind} check requires dc")
    return int(args["dc"])
