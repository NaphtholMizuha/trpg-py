from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ValidationError

TaskFamily = Literal[
    "single-target attack",
    "single-target spell",
    "area spell or area effect",
    "healing or buff",
    "unknown",
]
ResolutionMode = Literal["attack_damage", "save_damage", "heal", "unknown"]
ResourceMode = Literal["none", "spell_slot", "unknown"]
TargetingMode = Literal["direct_target", "center_on_target_position", "self_target", "unknown"]
SuccessRule = Literal["none", "half", "unknown"]


class TemplateQuerySchema(BaseModel):
    task_family: TaskFamily
    resolution_mode: ResolutionMode = "unknown"
    resource_mode: ResourceMode = "unknown"
    targeting_mode: TargetingMode = "unknown"
    success_rule: SuccessRule = "unknown"


TEMPLATE_ENUMS: dict[str, list[str]] = {
    "task_family": [
        "single-target attack",
        "single-target spell",
        "area spell or area effect",
        "healing or buff",
        "unknown",
    ],
    "resolution_mode": ["attack_damage", "save_damage", "heal", "unknown"],
    "resource_mode": ["none", "spell_slot", "unknown"],
    "targeting_mode": ["direct_target", "center_on_target_position", "self_target", "unknown"],
    "success_rule": ["none", "half", "unknown"],
}


DSL_TEMPLATES: list[dict[str, Any]] = [
    {
        "template_id": "single-target-attack.attack-damage",
        "task_family": "single-target attack",
        "resolution_mode": "attack_damage",
        "resource_mode": "none",
        "targeting_mode": "direct_target",
        "success_rule": "none",
        "description": "Single-target weapon or attack-roll attack that resolves hit first and damage second.",
        "step_order": ["check.attack", "damage.apply"],
        "dsl_skeleton": {
            "task_id": "{{task_id}}",
            "version": 1,
            "policy": {},
            "context": {},
            "steps": [
                {
                    "id": "attack_roll",
                    "type": "check",
                    "kind": "attack",
                    "args": {
                        "dice": "1d20",
                        "modifier": "{{attack_modifier}}",
                        "target_id": "{{target_id}}",
                        "target_ac_path": "{{target_ac_path}}",
                    },
                },
                {
                    "id": "apply_damage",
                    "type": "damage",
                    "kind": "apply",
                    "args": {
                        "targets": ["{{target_id}}"],
                        "damage": [
                            {
                                "dice": "{{damage_dice}}",
                                "bonus": "{{damage_bonus}}",
                                "damage_type": "{{damage_type}}",
                            }
                        ],
                    },
                },
            ],
        },
        "required_bindings": [
            "task_id",
            "target_id",
            "attack_modifier",
            "target_ac_path",
            "damage_dice",
            "damage_bonus",
            "damage_type",
        ],
        "binding_rules": {
            "target_id": "Use a concrete entity id like goblin_1, not a state path or $ref object.",
            "target_ac_path": "Use a raw state path like actors.goblin_1.ac.total, not state.actors.goblin_1.ac.total.",
            "attack_modifier": "Bind a numeric modifier, not a dice string or ref namespace literal.",
            "damage_dice": "Use a canonical dice string like 1d8 or 1d6.",
        },
        "common_mistakes": [
            "Do not invent select.target when the task already names a single explicit target.",
            "Do not put the attack bonus into the dice field; dice must stay 1d20.",
            "Do not prefix direct path fields with state.",
        ],
    },
    {
        "template_id": "single-target-spell.save-damage",
        "task_family": "single-target spell",
        "resolution_mode": "save_damage",
        "resource_mode": "none",
        "targeting_mode": "direct_target",
        "success_rule": "none",
        "description": "Single-target save-for-damage spell or cantrip with no spell-slot consumption.",
        "step_order": ["check.save", "damage.apply"],
        "dsl_skeleton": {
            "task_id": "{{task_id}}",
            "version": 1,
            "policy": {},
            "context": {},
            "steps": [
                {
                    "id": "saving_throw",
                    "type": "check",
                    "kind": "save",
                    "args": {
                        "dice": "1d20",
                        "ability": "{{save_ability}}",
                        "dc_path": "{{dc_path}}",
                        "target_id": "{{target_id}}",
                    },
                },
                {
                    "id": "apply_damage",
                    "type": "damage",
                    "kind": "apply",
                    "args": {
                        "targets": ["{{target_id}}"],
                        "damage": [
                            {
                                "dice": "{{damage_dice}}",
                                "damage_type": "{{damage_type}}",
                            }
                        ],
                        "save_result": {"$ref": "result.saving_throw"},
                        "on_save": "{{success_rule}}",
                    },
                },
            ],
        },
        "required_bindings": [
            "task_id",
            "target_id",
            "save_ability",
            "dc_path",
            "damage_dice",
            "damage_type",
            "success_rule",
        ],
        "binding_rules": {
            "save_ability": "Use engine ability names like dexterity, wisdom, constitution.",
            "dc_path": "Use a raw state path like actors.aldera.spell_dc.",
            "success_rule": "Use none or half; do not invent free-form save effect strings.",
        },
        "common_mistakes": [
            "Do not use dex or wis abbreviations when the engine expects full ability names.",
            "Do not omit dice from check.save.",
            "Do not hide spell damage behind amount='rule'.",
        ],
    },
    {
        "template_id": "area-spell.save-damage-half.spell-slot",
        "task_family": "area spell or area effect",
        "resolution_mode": "save_damage",
        "resource_mode": "spell_slot",
        "targeting_mode": "center_on_target_position",
        "success_rule": "half",
        "description": "Area spell centered on a target position, save-for-half damage, and spell-slot consumption.",
        "step_order": ["select.area", "check.save", "damage.apply", "resource.consume"],
        "dsl_skeleton": {
            "task_id": "{{task_id}}",
            "version": 1,
            "policy": {},
            "context": {},
            "steps": [
                {
                    "id": "select_area_targets",
                    "type": "select",
                    "kind": "area",
                    "args": {
                        "shape": "{{area_shape}}",
                        "radius": "{{area_radius}}",
                        "origin": {
                            "x": "{{origin_x_ref}}",
                            "y": "{{origin_y_ref}}",
                        },
                    },
                },
                {
                    "id": "saving_throw",
                    "type": "check",
                    "kind": "save",
                    "args": {
                        "dice": "1d20",
                        "ability": "{{save_ability}}",
                        "dc_path": "{{dc_path}}",
                        "targets": "{{selected_targets_ref}}",
                    },
                },
                {
                    "id": "apply_damage",
                    "type": "damage",
                    "kind": "apply",
                    "args": {
                        "targets": "{{selected_targets_ref}}",
                        "damage": [
                            {
                                "dice": "{{damage_dice}}",
                                "damage_type": "{{damage_type}}",
                            }
                        ],
                        "save_result": "{{save_result_ref}}",
                        "on_save": "{{success_rule}}",
                    },
                },
                {
                    "id": "consume_resource",
                    "type": "resource",
                    "kind": "consume",
                    "args": {
                        "path": "{{resource_path}}",
                        "cost": "{{resource_cost}}",
                    },
                },
            ],
        },
        "required_bindings": [
            "task_id",
            "area_shape",
            "area_radius",
            "origin_x_ref",
            "origin_y_ref",
            "save_ability",
            "dc_path",
            "selected_targets_ref",
            "damage_dice",
            "damage_type",
            "save_result_ref",
            "success_rule",
            "resource_path",
            "resource_cost",
        ],
        "binding_rules": {
            "origin_x_ref": "Use a $ref object such as {'$ref': 'state.actors.goblin_1.position.x'}, not a raw path string.",
            "origin_y_ref": "Use a $ref object such as {'$ref': 'state.actors.goblin_1.position.y'}, not a raw path string.",
            "selected_targets_ref": "Use {'$ref': 'result.select_area_targets.target_ids'} for area-selected targets.",
            "save_result_ref": "Use {'$ref': 'result.saving_throw'} to connect save results into damage.apply.",
            "dc_path": "Use a raw state path like actors.aldera.spell_dc.",
            "resource_path": "Use a raw state path like actors.aldera.spell_slots.level_3.current.",
        },
        "common_mistakes": [
            "Do not encode origin as a target id string.",
            "Do not prefix resource_path or dc_path with state.",
            "Do not invent save_effect or conditional_halving_on_save fields.",
        ],
    },
    {
        "template_id": "healing-or-buff.heal.spell-slot",
        "task_family": "healing or buff",
        "resolution_mode": "heal",
        "resource_mode": "spell_slot",
        "targeting_mode": "self_target",
        "success_rule": "none",
        "description": "Single-target healing spell that restores HP and consumes a spell slot.",
        "step_order": ["heal.apply", "resource.consume"],
        "dsl_skeleton": {
            "task_id": "{{task_id}}",
            "version": 1,
            "policy": {},
            "context": {},
            "steps": [
                {
                    "id": "apply_heal",
                    "type": "heal",
                    "kind": "apply",
                    "args": {
                        "targets": ["{{target_id}}"],
                        "healing": [
                            {
                                "dice": "{{healing_dice}}",
                                "bonus": "{{healing_bonus}}",
                            }
                        ],
                    },
                },
                {
                    "id": "consume_resource",
                    "type": "resource",
                    "kind": "consume",
                    "args": {
                        "path": "{{resource_path}}",
                        "cost": "{{resource_cost}}",
                    },
                },
            ],
        },
        "required_bindings": [
            "task_id",
            "target_id",
            "healing_dice",
            "healing_bonus",
            "resource_path",
            "resource_cost",
        ],
        "binding_rules": {
            "target_id": "Use a concrete target id like aldera.",
            "healing_dice": "Use a canonical dice string like 1d8.",
            "healing_bonus": "Bind a numeric bonus, not a formula string.",
            "resource_path": "Use a raw state path like actors.aldera.spell_slots.level_1.current.",
        },
        "common_mistakes": [
            "Prefer healing components over amount='roll(...)' strings when the dice spec is known.",
            "Do not prefix resource_path with state.",
        ],
    },
]


def list_template_ids() -> list[str]:
    return [entry["template_id"] for entry in DSL_TEMPLATES]


def query_template(
    *,
    task_family: TaskFamily,
    resolution_mode: ResolutionMode = "unknown",
    resource_mode: ResourceMode = "unknown",
    targeting_mode: TargetingMode = "unknown",
    success_rule: SuccessRule = "unknown",
) -> dict[str, Any]:
    normalized, error_result = validate_template_query(
        task_family=task_family,
        resolution_mode=resolution_mode,
        resource_mode=resource_mode,
        targeting_mode=targeting_mode,
        success_rule=success_rule,
    )
    if error_result is not None:
        return error_result
    assert normalized is not None
    if normalized["task_family"] == "unknown":
        return {
            "status": "no_match",
            "summary": "template lookup requires a supported task_family",
            "query": normalized,
            "available_task_families": TEMPLATE_ENUMS["task_family"],
            "available_template_ids": list_template_ids(),
        }

    best_entry: dict[str, Any] | None = None
    best_score = -1
    fallback_used = False
    for entry in DSL_TEMPLATES:
        if entry["task_family"] != normalized["task_family"]:
            continue
        score = 0
        entry_fallback = False
        for field in ("resolution_mode", "resource_mode", "targeting_mode", "success_rule"):
            requested = normalized[field]
            candidate = entry[field]
            if requested == "unknown":
                entry_fallback = True
                continue
            if requested == candidate:
                score += 1
                continue
            score = -1
            break
        if score > best_score:
            best_score = score
            best_entry = entry
            fallback_used = entry_fallback

    if best_entry is None:
        return {
            "status": "no_match",
            "summary": "no template matched the requested signature",
            "query": normalized,
            "available_template_ids": [
                entry["template_id"] for entry in DSL_TEMPLATES if entry["task_family"] == normalized["task_family"]
            ],
        }

    return {
        "status": "ok",
        "query": normalized,
        "fallback_used": fallback_used,
        "template_id": best_entry["template_id"],
        "description": best_entry["description"],
        "step_order": list(best_entry["step_order"]),
        "dsl_skeleton": best_entry["dsl_skeleton"],
        "required_bindings": list(best_entry["required_bindings"]),
        "binding_rules": dict(best_entry["binding_rules"]),
        "common_mistakes": list(best_entry["common_mistakes"]),
    }


def validate_template_query(
    *,
    task_family: Any,
    resolution_mode: Any = "unknown",
    resource_mode: Any = "unknown",
    targeting_mode: Any = "unknown",
    success_rule: Any = "unknown",
) -> tuple[dict[str, str] | None, dict[str, Any] | None]:
    raw_query = {
        "task_family": task_family,
        "resolution_mode": resolution_mode,
        "resource_mode": resource_mode,
        "targeting_mode": targeting_mode,
        "success_rule": success_rule,
    }
    try:
        validated = TemplateQuerySchema.model_validate(raw_query)
    except ValidationError as exc:
        return None, build_invalid_template_query_result(raw_query, exc)
    return validated.model_dump(), None


def build_invalid_template_query_result(raw_query: dict[str, Any], error: ValidationError) -> dict[str, Any]:
    invalid_fields: list[dict[str, Any]] = []
    seen_fields: set[str] = set()
    for detail in error.errors(include_url=False):
        loc = detail.get("loc", ())
        field = str(loc[0]) if loc else "unknown"
        if field in seen_fields:
            continue
        seen_fields.add(field)
        invalid_fields.append(
            {
                "field": field,
                "value": raw_query.get(field),
                "allowed_values": TEMPLATE_ENUMS.get(field, []),
                "message": detail.get("msg", "invalid enum value"),
            }
        )
    return {
        "status": "error",
        "summary": "invalid template query input",
        "error_type": "invalid_enum",
        "query": raw_query,
        "invalid_fields": invalid_fields,
    }
