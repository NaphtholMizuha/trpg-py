from __future__ import annotations

import json
import unittest
from pathlib import Path

from trpg_py import FixedDiceRoller, execute_task


ROOT = Path(__file__).resolve().parent.parent


def build_fireball_state() -> dict:
    return {
        "actors": {
            "wizard_1": {
                "id": "wizard_1",
                "side": "player",
                "alive": True,
                "position": {"x": 10, "y": 12},
                "spell_dc": 15,
                "hp": {"current": 22},
                "effects": [],
                "resources": {"spell_slots": {"3": 1}},
            },
            "goblin_1": {
                "id": "goblin_1",
                "side": "enemy",
                "alive": True,
                "position": {"x": 12, "y": 12},
                "hp": {"current": 18},
                "saves": {"dex": 2},
                "effects": [],
            },
            "goblin_2": {
                "id": "goblin_2",
                "side": "enemy",
                "alive": True,
                "position": {"x": 16, "y": 12},
                "hp": {"current": 18},
                "saves": {"dex": 0},
                "effects": [],
            },
            "ally_1": {
                "id": "ally_1",
                "side": "player",
                "alive": True,
                "position": {"x": 11, "y": 10},
                "hp": {"current": 11},
                "saves": {"dex": 1},
                "effects": [],
            },
        }
    }


def build_custom_layout_state() -> dict:
    return {
        "combatants": {
            "wizard_custom": {
                "meta": {"id": "wizard_custom"},
                "team": {"side": "player"},
                "status": {"alive": True},
                "traits": {"tags": ["caster", "humanoid"]},
                "space": {"grid": {"col": 10, "row": 12}},
                "numbers": {"magic": {"dc": 15}},
                "tracks": {"health": {"value": 22}},
                "status_lists": {"active_effects": []},
                "resources": {"spell_slots": {"3": 1}},
            },
            "goblin_custom_1": {
                "meta": {"id": "goblin_custom_1"},
                "team": {"side": "enemy"},
                "status": {"alive": True},
                "traits": {"tags": ["goblin"]},
                "space": {"grid": {"col": 12, "row": 12}},
                "numbers": {"saves": {"dexterity": 2}},
                "tracks": {"health": {"value": 18}},
                "status_lists": {"active_effects": []},
            },
            "goblin_custom_2": {
                "meta": {"id": "goblin_custom_2"},
                "team": {"side": "enemy"},
                "status": {"alive": True},
                "traits": {"tags": ["goblin"]},
                "space": {"grid": {"col": 16, "row": 12}},
                "numbers": {"saves": {"dexterity": 0}},
                "tracks": {"health": {"value": 18}},
                "status_lists": {"active_effects": []},
            },
            "ally_custom_1": {
                "meta": {"id": "ally_custom_1"},
                "team": {"side": "player"},
                "status": {"alive": True},
                "traits": {"tags": ["ally"]},
                "space": {"grid": {"col": 11, "row": 10}},
                "numbers": {"saves": {"dexterity": 1}},
                "tracks": {"health": {"value": 11}},
                "status_lists": {"active_effects": []},
            },
        }
    }


def build_line_state() -> dict:
    return {
        "actors": {
            "wizard_line": {
                "id": "wizard_line",
                "side": "player",
                "alive": True,
                "position": {"x": 0, "y": 0},
                "spell_dc": 15,
                "hp": {"current": 22},
                "effects": [],
                "resources": {"spell_slots": {"3": 1}},
            },
            "goblin_line_1": {
                "id": "goblin_line_1",
                "side": "enemy",
                "alive": True,
                "position": {"x": 5, "y": 0},
                "hp": {"current": 18},
                "saves": {"dex": 2},
                "effects": [],
            },
            "goblin_line_2": {
                "id": "goblin_line_2",
                "side": "enemy",
                "alive": True,
                "position": {"x": 8, "y": 2},
                "hp": {"current": 18},
                "saves": {"dex": 0},
                "effects": [],
            },
            "goblin_line_3": {
                "id": "goblin_line_3",
                "side": "enemy",
                "alive": True,
                "position": {"x": 3, "y": 4},
                "hp": {"current": 18},
                "saves": {"dex": 1},
                "effects": [],
            },
            "ally_line_1": {
                "id": "ally_line_1",
                "side": "player",
                "alive": True,
                "position": {"x": 6, "y": 0},
                "hp": {"current": 14},
                "saves": {"dex": 1},
                "effects": [],
            },
        }
    }


def build_cone_state() -> dict:
    return {
        "actors": {
            "wizard_cone": {
                "id": "wizard_cone",
                "side": "player",
                "alive": True,
                "position": {"x": 0, "y": 0},
                "spell_dc": 15,
                "hp": {"current": 18},
                "effects": [],
                "resources": {"spell_slots": {"1": 1}},
            },
            "goblin_cone_1": {
                "id": "goblin_cone_1",
                "side": "enemy",
                "alive": True,
                "position": {"x": 6, "y": 0},
                "hp": {"current": 14},
                "saves": {"dex": 1},
                "effects": [],
            },
            "goblin_cone_2": {
                "id": "goblin_cone_2",
                "side": "enemy",
                "alive": True,
                "position": {"x": 6, "y": 3},
                "hp": {"current": 14},
                "saves": {"dex": 4},
                "effects": [],
            },
            "goblin_cone_3": {
                "id": "goblin_cone_3",
                "side": "enemy",
                "alive": True,
                "position": {"x": 6, "y": 5},
                "hp": {"current": 14},
                "saves": {"dex": 2},
                "effects": [],
            },
        }
    }


class OperationTests(unittest.TestCase):
    def test_select_target_succeeds_when_target_is_in_range(self) -> None:
        document = json.loads((ROOT / "examples" / "goblin_scimitar_attack.json").read_text())
        state = {
            "actors": {
                "goblin_1": {
                    "id": "goblin_1",
                    "side": "enemy",
                    "alive": True,
                    "position": {"x": 1, "y": 1},
                    "hp": {"current": 7},
                    "attacks": {"scimitar": {"to_hit": 4}},
                },
                "hero_1": {
                    "id": "hero_1",
                    "side": "player",
                    "alive": True,
                    "position": {"x": 1, "y": 2},
                    "ac": 16,
                    "hp": {"current": 20},
                    "effects": [],
                    "saves": {"dex": 2},
                },
            }
        }
        report = execute_task(document, state, roller=FixedDiceRoller([15, 4]))
        self.assertEqual("success", report.status)
        self.assertEqual(["hero_1"], report.results["pick_target"]["target_ids"])

    def test_select_target_fails_when_target_is_out_of_range(self) -> None:
        document = json.loads((ROOT / "examples" / "goblin_scimitar_attack.json").read_text())
        state = {
            "actors": {
                "goblin_1": {
                    "id": "goblin_1",
                    "side": "enemy",
                    "alive": True,
                    "position": {"x": 1, "y": 1},
                    "hp": {"current": 7},
                    "attacks": {"scimitar": {"to_hit": 4}},
                },
                "hero_1": {
                    "id": "hero_1",
                    "side": "player",
                    "alive": True,
                    "position": {"x": 1, "y": 8},
                    "ac": 16,
                    "hp": {"current": 20},
                    "effects": [],
                    "saves": {"dex": 2},
                },
            }
        }
        report = execute_task(document, state, roller=FixedDiceRoller([15, 4]))
        self.assertEqual("failed", report.status)
        self.assertEqual("failed", report.step_reports[0].status)
        self.assertEqual("target_out_of_range", report.step_reports[0].error_code)
        self.assertIn("out of range", report.step_reports[0].error)

    def test_select_area_filters_enemy_targets(self) -> None:
        document = json.loads((ROOT / "examples" / "fireball.json").read_text())
        state = build_fireball_state()
        report = execute_task(document, state, roller=FixedDiceRoller([12, 18, 3, 3, 3, 3, 2, 2, 1, 1]))
        self.assertEqual(["goblin_1", "goblin_2"], report.results["select_targets"]["target_ids"])

    def test_select_area_fails_when_origin_is_out_of_range(self) -> None:
        document = json.loads((ROOT / "examples" / "fireball_out_of_range.json").read_text())
        state = build_fireball_state()
        report = execute_task(document, state, roller=FixedDiceRoller([]))
        self.assertEqual("failed", report.status)
        self.assertEqual("failed", report.step_reports[0].status)
        self.assertEqual("target_out_of_range", report.step_reports[0].error_code)
        self.assertIn("Area origin is out of range", report.step_reports[0].error)

    def test_select_area_can_succeed_with_empty_targets(self) -> None:
        document = json.loads((ROOT / "examples" / "fireball_empty.json").read_text())
        state = build_fireball_state()
        state["actors"]["goblin_1"]["position"] = {"x": 40, "y": 40}
        state["actors"]["goblin_2"]["position"] = {"x": 45, "y": 42}
        state["actors"]["ally_1"]["position"] = {"x": 42, "y": 41}
        report = execute_task(document, state, roller=FixedDiceRoller([]))
        self.assertEqual("success", report.status)
        self.assertEqual([], report.results["select_targets"]["target_ids"])
        self.assertEqual([], report.results["dex_save"]["target_ids"])
        self.assertEqual({}, report.results["fire_damage"]["per_target"])
        self.assertEqual(0, state["actors"]["wizard_1"]["resources"]["spell_slots"]["3"])
        self.assertEqual(
            "actors.wizard_1.resources.spell_slots.3",
            report.applied_changes[0].path,
        )

    def test_damage_halves_on_successful_save(self) -> None:
        document = json.loads((ROOT / "examples" / "fireball.json").read_text())
        state = build_fireball_state()
        report = execute_task(document, state, roller=FixedDiceRoller([12, 18, 3, 3, 3, 3, 2, 2, 1, 1]))
        self.assertEqual("success", report.status)
        self.assertEqual(0, state["actors"]["goblin_1"]["hp"]["current"])
        self.assertEqual(9, state["actors"]["goblin_2"]["hp"]["current"])

    def test_damage_on_save_none_prevents_damage_for_successful_target(self) -> None:
        document = {
            "task_id": "save_for_none",
            "version": 1,
            "steps": [
                {
                    "id": "damage",
                    "type": "damage",
                    "kind": "apply",
                    "args": {
                        "targets": ["hero_1"],
                        "damage": [{"dice": "1d8", "bonus": 2, "damage_type": "radiant"}],
                        "save_result": {"target_results": {"hero_1": {"success": True}}},
                        "on_save": "none"
                    },
                }
            ],
        }
        state = {"actors": {"hero_1": {"hp": {"current": 20}}}}
        report = execute_task(document, state, roller=FixedDiceRoller([6]))
        self.assertEqual("success", report.status)
        self.assertEqual(20, state["actors"]["hero_1"]["hp"]["current"])
        self.assertEqual(0, report.results["damage"]["per_target"]["hero_1"]["final_total"])

    def test_critical_damage_rolls_extra_dice_without_repeating_bonus(self) -> None:
        document = {
            "task_id": "critical_damage",
            "version": 1,
            "steps": [
                {
                    "id": "damage",
                    "type": "damage",
                    "kind": "apply",
                    "args": {
                        "targets": ["hero_1"],
                        "damage": [{"dice": "1d8", "bonus": 3, "damage_type": "slashing"}],
                        "is_critical": True
                    },
                }
            ],
        }
        state = {"actors": {"hero_1": {"hp": {"current": 20}}}}
        report = execute_task(document, state, roller=FixedDiceRoller([4, 7]))
        self.assertEqual("success", report.status)
        self.assertEqual(6, state["actors"]["hero_1"]["hp"]["current"])
        component = report.results["damage"]["per_target"]["hero_1"]["components"][0]
        self.assertEqual([4, 7], component["rolls"])
        self.assertEqual(14, component["total"])

    def test_select_area_line_matches_targets_in_path(self) -> None:
        document = json.loads((ROOT / "examples" / "lightning_bolt_line.json").read_text())
        state = build_line_state()
        report = execute_task(document, state, roller=FixedDiceRoller([12, 18, 3, 3, 3, 3, 2, 2, 1, 1]))
        self.assertEqual(["goblin_line_1", "goblin_line_2"], report.results["select_targets"]["target_ids"])

    def test_select_area_cone_matches_targets_in_arc(self) -> None:
        document = json.loads((ROOT / "examples" / "burning_hands_cone.json").read_text())
        state = build_cone_state()
        report = execute_task(document, state, roller=FixedDiceRoller([12, 18, 4, 3, 2]))
        self.assertEqual(["goblin_cone_1", "goblin_cone_2"], report.results["select_targets"]["target_ids"])

    def test_select_area_target_only_matches_origin_cell(self) -> None:
        document = {
            "task_id": "target_select",
            "version": 1,
            "steps": [
                {
                    "id": "select_target",
                    "type": "select",
                    "kind": "area",
                    "args": {
                        "shape": "target",
                        "origin": {"x": 2, "y": 2},
                        "include_side": ["enemy"],
                        "must_be_alive": True
                    },
                }
            ],
        }
        state = {
            "actors": {
                "target_here": {
                    "id": "target_here",
                    "side": "enemy",
                    "alive": True,
                    "position": {"x": 2, "y": 2},
                },
                "target_elsewhere": {
                    "id": "target_elsewhere",
                    "side": "enemy",
                    "alive": True,
                    "position": {"x": 2, "y": 3},
                },
            }
        }
        report = execute_task(document, state, roller=FixedDiceRoller([]))
        self.assertEqual(["target_here"], report.results["select_target"]["target_ids"])

    def test_resource_and_effect_operations(self) -> None:
        document = {
            "task_id": "resource_and_effect",
            "version": 1,
            "steps": [
                {
                    "id": "spend_slot",
                    "type": "resource",
                    "kind": "consume",
                    "args": {"path": "actors.wizard_1.resources.spell_slots.1", "cost": 1},
                },
                {
                    "id": "add_bless",
                    "type": "effect",
                    "kind": "add",
                    "args": {
                        "targets": ["hero_1"],
                        "effect": {"id": "bless", "duration_rounds": 10, "source": "cleric_1"},
                    },
                },
                {
                    "id": "remove_bless",
                    "type": "effect",
                    "kind": "remove",
                    "args": {"targets": ["hero_1"], "effect_id": "bless"},
                },
            ],
        }
        state = {
            "actors": {
                "wizard_1": {"resources": {"spell_slots": {"1": 1}}},
                "hero_1": {"effects": []},
            }
        }
        report = execute_task(document, state, roller=FixedDiceRoller([]))
        self.assertEqual("success", report.status)
        self.assertEqual(0, state["actors"]["wizard_1"]["resources"]["spell_slots"]["1"])
        self.assertEqual([], state["actors"]["hero_1"]["effects"])

    def test_insufficient_resource_fails_without_changing_state(self) -> None:
        document = {
            "task_id": "resource_fail",
            "version": 1,
            "steps": [
                {
                    "id": "spend_slot",
                    "type": "resource",
                    "kind": "consume",
                    "args": {"path": "actors.wizard_1.resources.spell_slots.1", "cost": 1},
                }
            ],
        }
        state = {"actors": {"wizard_1": {"resources": {"spell_slots": {"1": 0}}}}}
        report = execute_task(document, state, roller=FixedDiceRoller([]))
        self.assertEqual("failed", report.status)
        self.assertEqual(0, state["actors"]["wizard_1"]["resources"]["spell_slots"]["1"])

    def test_heal_caps_at_default_hp_max(self) -> None:
        document = {
            "task_id": "heal_cap_default",
            "version": 1,
            "steps": [
                {
                    "id": "heal_target",
                    "type": "heal",
                    "kind": "apply",
                    "args": {"targets": ["hero_1"], "amount": 5},
                }
            ],
        }
        state = {"actors": {"hero_1": {"hp": {"current": 7, "max": 10}}}}
        report = execute_task(document, state, roller=FixedDiceRoller([]))
        self.assertEqual("success", report.status)
        self.assertEqual(10, state["actors"]["hero_1"]["hp"]["current"])
        self.assertEqual(3, report.results["heal_target"]["per_target"]["hero_1"]["final_total"])
        self.assertEqual(5, report.results["heal_target"]["per_target"]["hero_1"]["requested_total"])
        self.assertTrue(report.results["heal_target"]["per_target"]["hero_1"]["capped"])

    def test_heal_can_use_explicit_max_hp_path(self) -> None:
        document = {
            "task_id": "heal_cap_direct_path",
            "version": 1,
            "steps": [
                {
                    "id": "heal_target",
                    "type": "heal",
                    "kind": "apply",
                    "args": {
                        "targets": ["hero_1"],
                        "amount": 5,
                        "target_hp_max_path": "actors.hero_1.stats.health_cap",
                    },
                }
            ],
        }
        state = {"actors": {"hero_1": {"hp": {"current": 7}, "stats": {"health_cap": 10}}}}
        report = execute_task(document, state, roller=FixedDiceRoller([]))
        self.assertEqual("success", report.status)
        self.assertEqual(10, state["actors"]["hero_1"]["hp"]["current"])
        self.assertEqual(10, report.results["heal_target"]["per_target"]["hero_1"]["max_hp"])

    def test_heal_can_use_custom_max_hp_path_template(self) -> None:
        document = {
            "task_id": "heal_cap_template",
            "version": 1,
            "steps": [
                {
                    "id": "heal_target",
                    "type": "heal",
                    "kind": "apply",
                    "args": {
                        "targets": ["target_1"],
                        "amount": 5,
                        "target_hp_path_template": "combatants.{target_id}.tracks.health.value",
                        "target_hp_max_path_template": "combatants.{target_id}.tracks.health.max",
                    },
                }
            ],
        }
        state = {"combatants": {"target_1": {"tracks": {"health": {"value": 7, "max": 10}}}}}
        report = execute_task(document, state, roller=FixedDiceRoller([]))
        self.assertEqual("success", report.status)
        self.assertEqual(10, state["combatants"]["target_1"]["tracks"]["health"]["value"])
        self.assertTrue(report.results["heal_target"]["per_target"]["target_1"]["capped"])

    def test_custom_layout_example_uses_field_map_and_templates(self) -> None:
        document = json.loads((ROOT / "examples" / "custom_layout_fireburst.json").read_text())
        state = build_custom_layout_state()
        report = execute_task(document, state, roller=FixedDiceRoller([12, 18, 3, 3, 3, 3, 2, 2, 1, 1]))
        self.assertEqual("success", report.status)
        self.assertEqual(["goblin_custom_1", "goblin_custom_2"], report.results["select_targets"]["target_ids"])
        self.assertEqual(0, state["combatants"]["goblin_custom_1"]["tracks"]["health"]["value"])
        self.assertEqual(9, state["combatants"]["goblin_custom_2"]["tracks"]["health"]["value"])
        self.assertEqual(
            [{"id": "burning", "source": "wizard_custom", "duration_rounds": 1}],
            state["combatants"]["goblin_custom_1"]["status_lists"]["active_effects"],
        )
        self.assertEqual(
            [{"id": "burning", "source": "wizard_custom", "duration_rounds": 1}],
            state["combatants"]["goblin_custom_2"]["status_lists"]["active_effects"],
        )

    def test_effect_can_use_custom_effects_path_template(self) -> None:
        document = {
            "task_id": "custom_effect_path",
            "version": 1,
            "steps": [
                {
                    "id": "add_effect",
                    "type": "effect",
                    "kind": "add",
                    "args": {
                        "targets": ["target_1"],
                        "effects_path_template": "combatants.{target_id}.condition_store.current",
                        "effect": {"id": "faerie_fire", "source": "caster_1", "duration_rounds": 10},
                    },
                }
            ],
        }
        state = {"combatants": {"target_1": {"condition_store": {"current": []}}}}
        report = execute_task(document, state, roller=FixedDiceRoller([]))
        self.assertEqual("success", report.status)
        self.assertEqual(
            [{"id": "faerie_fire", "source": "caster_1", "duration_rounds": 10}],
            state["combatants"]["target_1"]["condition_store"]["current"],
        )


if __name__ == "__main__":
    unittest.main()
