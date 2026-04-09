from __future__ import annotations

from typing import Any


DSL_SHAPE_CATALOG: dict[tuple[str, str], dict[str, Any]] = {
    (
        "select",
        "area",
    ): {
        "required_args": ["shape", "origin"],
        "allowed_args": [
            "entity_pool",
            "exclude_ids",
            "exclude_tags",
            "field_map",
            "include_side",
            "include_sides",
            "include_tags",
            "length",
            "max_targets",
            "must_be_alive",
            "origin",
            "radius",
            "shape",
            "targeting",
            "width",
            "direction",
            "angle",
        ],
        "example_step": {
            "id": "select_area_targets",
            "type": "select",
            "kind": "area",
            "args": {
                "shape": "sphere",
                "radius": 20,
                "origin": {
                    "x": {"$ref": "state.actors.goblin_1.position.x"},
                    "y": {"$ref": "state.actors.goblin_1.position.y"},
                },
            },
        },
        "common_mistakes": [
            "Do not encode shape as an object such as {'type': 'sphere', 'radius': 20}. Use a string shape plus separate radius/length fields.",
            "origin must be an object with x and y, not a target id string.",
        ],
        "notes": [
            "sphere uses radius",
            "line uses length and optional width/direction",
            "cone uses length and optional angle/direction",
        ],
    },
    (
        "check",
        "save",
    ): {
        "required_args": ["dice", "ability"],
        "allowed_args": ["ability", "dc", "dc_path", "dice", "modifier", "modifier_path", "modifier_path_template", "target_id", "targets"],
        "one_of_required": [["dc", "dc_path"]],
        "example_step": {
            "id": "dexterity_save",
            "type": "check",
            "kind": "save",
            "args": {
                "dice": "1d20",
                "ability": "dexterity",
                "dc_path": "actors.aldera.spell_dc",
                "targets": {"$ref": "result.select_area_targets.target_ids"},
            },
        },
        "common_mistakes": [
            "Use ability, not save_ability.",
            "Use dc or dc_path. Do not hide the save threshold in unrelated fields.",
            "dc_path should be a state path like actors.aldera.spell_dc, not state.actors.aldera.spell_dc.",
        ],
        "notes": [
            "targets or target_id are optional but usually needed to bind the save to selected targets",
        ],
    },
    (
        "check",
        "attack",
    ): {
        "required_args": ["dice"],
        "allowed_args": ["dice", "modifier", "modifier_path", "modifier_path_template", "target_ac", "target_ac_path", "target_ac_path_template", "target_id", "targets"],
        "one_of_required": [["target_ac", "target_ac_path", "target_ac_path_template", "target_id", "targets"]],
        "example_step": {
            "id": "attack_roll",
            "type": "check",
            "kind": "attack",
            "args": {
                "dice": "1d20",
                "modifier": 7,
                "target_id": "goblin_1",
                "target_ac": 15,
            },
        },
        "common_mistakes": [
            "check.attack requires dice and some form of target identity or target AC source.",
            "Do not hide attack resolution inside custom invoke or calculate steps.",
        ],
        "notes": [],
    },
    (
        "damage",
        "apply",
    ): {
        "required_args": ["targets", "damage"],
        "allowed_args": ["damage", "is_critical", "on_save", "per_target_roll", "save_result", "target_hp_path", "target_hp_path_template", "target_id", "targets"],
        "example_step": {
            "id": "apply_fireball_damage",
            "type": "damage",
            "kind": "apply",
            "args": {
                "targets": {"$ref": "result.select_area_targets.target_ids"},
                "damage": [
                    {
                        "dice": "8d6",
                        "damage_type": "fire",
                    }
                ],
                "save_result": {"$ref": "result.dexterity_save"},
                "on_save": "half",
            },
        },
        "common_mistakes": [
            "Use damage as an object or list of objects containing dice/bonus/damage_type.",
            "Do not use amount, type, conditional_halving_on_save, or save_effect as custom keys.",
            "For save-based damage, use save_result plus on_save='half' or on_save='none'.",
        ],
        "notes": [],
    },
    (
        "resource",
        "consume",
    ): {
        "required_args": ["path"],
        "allowed_args": ["cost", "path"],
        "example_step": {
            "id": "consume_spell_slot",
            "type": "resource",
            "kind": "consume",
            "args": {
                "path": "actors.aldera.spell_slots.level_3.current",
                "cost": 1,
            },
        },
        "common_mistakes": [
            "path should be a state path like actors.aldera.spell_slots.level_3.current, not state.actors.aldera.spell_slots.level_3.current.",
        ],
        "notes": [],
    },
    (
        "state",
        "set",
    ): {
        "required_args": ["path"],
        "allowed_args": ["path", "value"],
        "example_step": {
            "id": "record_state",
            "type": "state",
            "kind": "set",
            "args": {
                "path": "actors.aldera.ac",
                "value": 18,
            },
        },
        "common_mistakes": [
            "state.set requires path and usually a value.",
        ],
        "notes": [],
    },
    (
        "state",
        "adjust",
    ): {
        "required_args": ["path"],
        "allowed_args": ["delta", "path"],
        "example_step": {
            "id": "adjust_hp",
            "type": "state",
            "kind": "adjust",
            "args": {
                "path": "actors.goblin_1.hp.current",
                "delta": -7,
            },
        },
        "common_mistakes": [
            "state.adjust requires path and typically delta.",
        ],
        "notes": [],
    },
}


def build_expected_shape(step_type: str, step_kind: str) -> dict[str, Any] | None:
    entry = DSL_SHAPE_CATALOG.get((step_type, step_kind))
    if entry is None:
        return None
    expected = {
        "step_type": step_type,
        "step_kind": step_kind,
        "required_args": list(entry.get("required_args", [])),
        "allowed_args": list(entry.get("allowed_args", [])),
        "canonical_example": entry.get("example_step"),
        "common_mistakes": list(entry.get("common_mistakes", [])),
        "notes": list(entry.get("notes", [])),
    }
    if "one_of_required" in entry:
        expected["one_of_required"] = [list(group) for group in entry["one_of_required"]]
    return expected
