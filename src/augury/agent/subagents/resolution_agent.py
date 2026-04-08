from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Any

from augury.agent.models import ErrorInfo, ResolutionBundle
from augury.store import read
from augury.store.compat import has_path


@dataclass(slots=True)
class ResolutionAgentDependencies:
    lint_tool: Any
    execute_tool: Any


class ResolutionAgent:
    def __init__(self, dependencies: ResolutionAgentDependencies) -> None:
        self.dependencies = dependencies

    def run(self, payload: dict[str, Any]) -> ResolutionBundle:
        state = payload.get("state") or {}
        instruction = str(payload.get("instruction", ""))
        context_bundle = payload.get("context_bundle") or {}
        task_document = payload.get("task_document")
        blocked_reasons: list[str] = []

        if not isinstance(task_document, dict):
            task_document, blocked_reasons = build_candidate_task_document(
                instruction=instruction,
                state=state,
                context_bundle=context_bundle,
            )

        if task_document is None:
            return ResolutionBundle(status="blocked", blocked_reasons=blocked_reasons)

        lint_result = self.dependencies.lint_tool.invoke({"task_document": task_document})
        if lint_result.get("status") != "valid":
            blocked_reasons.append(lint_result.get("summary") or "lint failed")
            return ResolutionBundle(
                status="blocked",
                task_document=task_document,
                lint_result=lint_result,
                blocked_reasons=blocked_reasons,
            )

        execute_result = self.dependencies.execute_tool.invoke({"task_document": task_document})
        execution_report = execute_result.get("execution_report")
        state_changes = list(execute_result.get("state_changes", []))
        if execute_result.get("status") != "success":
            blocked_reasons.append(_summarize_execution_failure(execute_result))
            return ResolutionBundle(
                status="blocked",
                task_document=task_document,
                lint_result=lint_result,
                execution_report=execution_report,
                state_changes=state_changes,
                blocked_reasons=blocked_reasons,
            )

        return ResolutionBundle(
            status="ready",
            task_document=task_document,
            lint_result=lint_result,
            execution_report=execution_report,
            state_changes=state_changes,
        )


def build_candidate_task_document(
    *,
    instruction: str,
    state: dict[str, Any],
    context_bundle: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    action = context_bundle.get("action")
    resolved_entities = context_bundle.get("resolved_entities") or {}
    derived_context = context_bundle.get("derived_context") or {}
    actor_id = resolved_entities.get("actor_id")
    target_id = resolved_entities.get("target_id")
    area_point = derived_context.get("area_point")

    if action == "weapon_attack" and actor_id and target_id:
        return _build_weapon_attack_document(state, actor_id=actor_id, target_id=target_id, instruction=instruction), []
    if action == "spell_attack" and actor_id and target_id:
        return _build_spell_attack_document(actor_id=actor_id, target_id=target_id, instruction=instruction), []
    if action == "heal_spell" and actor_id and target_id:
        return _build_heal_document(actor_id=actor_id, target_id=target_id, instruction=instruction), []
    if action == "area_spell" and actor_id and target_id:
        if "闪电束" in instruction:
            return _build_lightning_bolt_document(state, actor_id=actor_id, target_id=target_id, instruction=instruction), []
        if area_point is None and "所在位置" not in instruction and "位置" not in instruction:
            return None, ["范围法术仍缺少明确爆点。"]
        return _build_fireball_document(
            state,
            actor_id=actor_id,
            target_id=target_id,
            instruction=instruction,
            area_point=area_point,
        ), []
    if action == "record_state" and actor_id:
        return _build_record_document(state, actor_id=actor_id, instruction=instruction), []
    return None, ["当前最小求解器还不能把这条 instruction lower 成可执行 TaskDocument。"]


def _build_weapon_attack_document(
    state: dict[str, Any],
    *,
    actor_id: str,
    target_id: str,
    instruction: str,
) -> dict[str, Any]:
    if "长剑" in instruction:
        attack_path = f"actors.{actor_id}.attacks.longsword"
        fallback_damage = [{"dice": "1d8", "bonus": 4, "damage_type": "slashing"}]
    elif "短弓" in instruction:
        attack_path = f"actors.{actor_id}.attacks.shortbow"
        fallback_damage = [{"dice": "1d6", "bonus": 2, "damage_type": "piercing"}]
    else:
        attack_path = f"actors.{actor_id}.attacks.scimitar"
        fallback_damage = [{"dice": "1d6", "bonus": 2, "damage_type": "slashing"}]
    damage = _read_or_default(state, f"{attack_path}.damage", fallback_damage)
    range_limit = _resolve_weapon_range(state, attack_path)
    return {
        "task_id": f"planner.attack-{actor_id}-{target_id}",
        "version": 1,
        "policy": {"ruleset": "dnd5e-2014"},
        "context": {"actor_id": actor_id, "target_id": target_id},
        "steps": [
            {
                "id": "pick_target",
                "type": "select",
                "kind": "target",
                "args": {
                    "source": {"$ref": "context.target_id"},
                    "entity_pool": {"$ref": "state.actors"},
                    "targeting": {
                        "source_position": {"$ref": f"state.actors.{actor_id}.position"},
                        "max_range": range_limit,
                        "range_metric": "euclidean",
                    },
                },
            },
            {
                "id": "attack_roll",
                "type": "check",
                "kind": "attack",
                "tags": ["nat"],
                "args": {
                    "dice": "1d20",
                    "modifier": {"$ref": f"state.{attack_path}.to_hit"},
                    "target_id": {"$ref": "context.target_id"},
                    "target_ac": {"$ref": _resolve_ac_ref(state, target_id)},
                },
            },
            {
                "id": "apply_damage",
                "type": "damage",
                "kind": "apply",
                "when": {"$ref": "result.attack_roll.outcome", "in": ["success", "crit_success"]},
                "args": {
                    "targets": {"$ref": "result.pick_target.target_ids"},
                    "damage": damage,
                    "is_critical": {"$ref": "result.attack_roll.outcome", "eq": "crit_success"},
                },
            },
        ],
    }


def _build_spell_attack_document(
    *,
    actor_id: str,
    target_id: str,
    instruction: str,
) -> dict[str, Any]:
    return {
        "task_id": f"planner.spell-attack-{actor_id}-{target_id}",
        "version": 1,
        "policy": {"ruleset": "dnd5e-2014"},
        "context": {"actor_id": actor_id, "target_id": target_id},
        "steps": [
            {
                "id": "spell_attack_roll",
                "type": "check",
                "kind": "attack",
                "tags": ["nat"],
                "args": {
                    "dice": "1d20",
                    "modifier": {"$ref": f"state.actors.{actor_id}.spell_attack_bonus"},
                    "target_id": {"$ref": "context.target_id"},
                    "target_ac": {"$ref": f"state.actors.{target_id}.ac.total"},
                },
            },
            {
                "id": "apply_spell_damage",
                "type": "damage",
                "kind": "apply",
                "when": {"$ref": "result.spell_attack_roll.outcome", "in": ["success", "crit_success"]},
                "args": {
                    "targets": [{"$ref": "context.target_id"}],
                    "damage": [{"dice": "2d10", "bonus": 0, "damage_type": "fire"}],
                    "is_critical": {"$ref": "result.spell_attack_roll.outcome", "eq": "crit_success"},
                },
            },
        ],
    }


def _build_heal_document(
    *,
    actor_id: str,
    target_id: str,
    instruction: str,
) -> dict[str, Any]:
    return {
        "task_id": f"planner.heal-{actor_id}-{target_id}",
        "version": 1,
        "policy": {"ruleset": "dnd5e-2014"},
        "context": {"actor_id": actor_id, "target_id": target_id},
        "steps": [
            {
                "id": "pick_target",
                "type": "select",
                "kind": "target",
                "args": {"source": {"$ref": "context.target_id"}},
            },
            {
                "id": "spend_slot",
                "type": "resource",
                "kind": "consume",
                "args": {
                    "path": f"actors.{actor_id}.spell_slots.level_1.current",
                    "cost": 1,
                },
            },
            {
                "id": "apply_heal",
                "type": "heal",
                "kind": "apply",
                "args": {
                    "targets": {"$ref": "result.pick_target.target_ids"},
                    "amount": 8,
                },
            },
        ],
    }


def _build_fireball_document(
    state: dict[str, Any],
    *,
    actor_id: str,
    target_id: str,
    instruction: str,
    area_point: str | None = None,
) -> dict[str, Any]:
    origin = _resolve_fireball_origin(state, target_id=target_id, area_point=area_point)
    return {
        "task_id": f"planner.fireball-{actor_id}-{target_id}",
        "version": 1,
        "policy": {"ruleset": "dnd5e-2014"},
        "context": {"caster_id": actor_id, "origin": origin},
        "steps": [
            {
                "id": "select_targets",
                "type": "select",
                "kind": "area",
                "args": {
                    "shape": "sphere",
                    "radius": 20,
                    "origin": {"$ref": "context.origin"},
                    "include_side": ["enemy"],
                    "exclude_ids": [{"$ref": "context.caster_id"}],
                    "must_be_alive": True,
                    "targeting": {
                        "source_position": {"$ref": f"state.actors.{actor_id}.position"},
                        "max_range": 150,
                        "range_metric": "euclidean",
                    },
                },
            },
            {
                "id": "spend_slot",
                "type": "resource",
                "kind": "consume",
                "args": {"path": f"actors.{actor_id}.spell_slots.level_3.current", "cost": 1},
            },
            {
                "id": "dex_save",
                "type": "check",
                "kind": "save",
                "tags": ["nat"],
                "args": {
                    "targets": {"$ref": "result.select_targets.target_ids"},
                    "dice": "1d20",
                    "ability": "dex",
                    "modifier_path_template": "actors.{target_id}.abilities.dex.save",
                    "dc_path": f"actors.{actor_id}.spell_dc",
                },
            },
            {
                "id": "fire_damage",
                "type": "damage",
                "kind": "apply",
                "args": {
                    "targets": {"$ref": "result.select_targets.target_ids"},
                    "damage": [{"dice": "8d6", "bonus": 0, "damage_type": "fire"}],
                    "save_result": {"$ref": "result.dex_save"},
                    "on_save": "half",
                },
            },
        ],
    }


def _resolve_fireball_origin(
    state: dict[str, Any],
    *,
    target_id: str,
    area_point: str | None,
) -> dict[str, Any]:
    if area_point in {None, "", "use_target_position"}:
        return _read_or_default(state, f"actors.{target_id}.position", {"x": 0, "y": 0})
    parsed = _parse_point_literal(area_point)
    if parsed is not None:
        return parsed
    if has_path(state, f"actors.{area_point}.position"):
        return _read_or_default(state, f"actors.{area_point}.position", {"x": 0, "y": 0})
    return _read_or_default(state, f"actors.{target_id}.position", {"x": 0, "y": 0})


def _parse_point_literal(value: str) -> dict[str, Any] | None:
    text = value.strip()
    if not (text.startswith("(") and text.endswith(")")):
        return None
    try:
        x_str, y_str = [item.strip() for item in text[1:-1].split(",", maxsplit=1)]
        return {"x": float(x_str), "y": float(y_str)}
    except Exception:
        return None


def _build_lightning_bolt_document(
    state: dict[str, Any],
    *,
    actor_id: str,
    target_id: str,
    instruction: str,
) -> dict[str, Any]:
    origin = _read_or_default(state, f"actors.{actor_id}.position", {"x": 0, "y": 0})
    target_position = _read_or_default(state, f"actors.{target_id}.position", origin)
    direction = _direction_between(origin, target_position)
    return {
        "task_id": f"planner.lightning-bolt-{actor_id}-{target_id}",
        "version": 1,
        "policy": {"ruleset": "dnd5e-2014"},
        "context": {"caster_id": actor_id, "origin": origin},
        "steps": [
            {
                "id": "select_targets",
                "type": "select",
                "kind": "area",
                "args": {
                    "shape": "line",
                    "origin": {"$ref": "context.origin"},
                    "length": 100,
                    "width": 5,
                    "direction": direction,
                    "include_side": ["enemy"],
                    "exclude_ids": [{"$ref": "context.caster_id"}],
                    "must_be_alive": True,
                    "targeting": {
                        "source_position": {"$ref": f"state.actors.{actor_id}.position"},
                        "max_range": 100,
                        "range_metric": "euclidean",
                    },
                },
            },
            {
                "id": "spend_slot",
                "type": "resource",
                "kind": "consume",
                "args": {"path": f"actors.{actor_id}.spell_slots.level_3.current", "cost": 1},
            },
            {
                "id": "dex_save",
                "type": "check",
                "kind": "save",
                "tags": ["nat"],
                "args": {
                    "targets": {"$ref": "result.select_targets.target_ids"},
                    "dice": "1d20",
                    "ability": "dex",
                    "modifier_path_template": "actors.{target_id}.abilities.dex.save",
                    "dc_path": f"actors.{actor_id}.spell_dc",
                },
            },
            {
                "id": "line_damage",
                "type": "damage",
                "kind": "apply",
                "args": {
                    "targets": {"$ref": "result.select_targets.target_ids"},
                    "damage": [{"dice": "8d6", "bonus": 0, "damage_type": "lightning"}],
                    "save_result": {"$ref": "result.dex_save"},
                    "on_save": "half",
                },
            },
        ],
    }


def _build_record_document(
    state: dict[str, Any],
    *,
    actor_id: str,
    instruction: str,
) -> dict[str, Any]:
    source_path = _resolve_ac_ref(state, actor_id).removeprefix("state.")
    snapshot_value = read(state, source_path)
    return {
        "task_id": f"planner.record-{actor_id}-ac",
        "version": 1,
        "policy": {"ruleset": "dnd5e-2014"},
        "context": {"actor_id": actor_id},
        "steps": [
            {
                "id": "record_ac",
                "type": "state",
                "kind": "set",
                "args": {
                    "path": f"planner_memory.{actor_id}.ac_snapshot",
                    "value": snapshot_value,
                },
            }
        ],
    }


def _read_or_default(state: dict[str, Any], path: str, default: Any) -> Any:
    if has_path(state, path):
        return read(state, path)
    return default


def _resolve_ac_ref(state: dict[str, Any], target_id: str) -> str:
    total_path = f"state.actors.{target_id}.ac.total"
    if has_path(state, total_path.removeprefix("state.")):
        return total_path
    return f"state.actors.{target_id}.ac"


def _resolve_weapon_range(state: dict[str, Any], attack_path: str) -> int:
    reach_path = f"{attack_path}.reach"
    if has_path(state, reach_path):
        return int(read(state, reach_path))
    range_path = f"{attack_path}.range"
    if has_path(state, range_path):
        raw_range = str(read(state, range_path))
        if "/" in raw_range:
            raw_range = raw_range.split("/", maxsplit=1)[0]
        return int(raw_range)
    return 5


def _direction_between(origin: dict[str, Any], target: dict[str, Any]) -> dict[str, float]:
    dx = float(target["x"]) - float(origin["x"])
    dy = float(target["y"]) - float(origin["y"])
    length = hypot(dx, dy) or 1.0
    return {"x": dx / length, "y": dy / length}


def _summarize_execution_failure(execute_result: dict[str, Any]) -> str:
    if execute_result.get("status") == "validation_failed":
        return "execute rejected the task document during validation"
    if execute_result.get("status") == "failed":
        report = execute_result.get("execution_report") or {}
        return str(report.get("error") or "execution failed")
    error = execute_result.get("error") or {}
    return f"{error.get('type', 'error')}: {error.get('message', '')}"
