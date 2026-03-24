from __future__ import annotations

import unittest

from trpg_py import FixedDiceRoller, execute_task, validate_task_document
from trpg_py.errors import ValidationError


class ValidationAndExecutorTests(unittest.TestCase):
    def test_missing_task_id_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_task_document({"version": 1, "steps": []})

    def test_future_result_reference_is_rejected(self) -> None:
        document = {
            "task_id": "invalid_ref",
            "version": 1,
            "steps": [
                {
                    "id": "damage",
                    "type": "damage",
                    "kind": "apply",
                    "args": {
                        "targets": ["hero_1"],
                        "damage": [{"dice": "1d6", "bonus": 0, "damage_type": "fire"}],
                        "is_critical": {"$ref": "result.attack.outcome", "eq": "crit_success"},
                    },
                },
                {
                    "id": "attack",
                    "type": "check",
                    "kind": "attack",
                    "tags": ["nat"],
                    "args": {"dice": "1d20", "modifier": 5, "target_id": "hero_1", "target_ac": 10},
                },
            ],
        }
        with self.assertRaises(ValidationError):
            validate_task_document(document)

    def test_when_clause_skips_later_step(self) -> None:
        document = {
            "task_id": "skip_damage",
            "version": 1,
            "context": {"target_id": "hero_1"},
            "steps": [
                {
                    "id": "attack",
                    "type": "check",
                    "kind": "attack",
                    "tags": ["nat"],
                    "args": {
                        "dice": "1d20",
                        "modifier": 1,
                        "target_id": {"$ref": "context.target_id"},
                        "target_ac": 20,
                    },
                },
                {
                    "id": "damage",
                    "type": "damage",
                    "kind": "apply",
                    "when": {"$ref": "result.attack.outcome", "in": ["success", "crit_success"]},
                    "args": {
                        "targets": ["hero_1"],
                        "damage": [{"dice": "1d6", "bonus": 0, "damage_type": "slashing"}],
                    },
                },
            ],
        }
        state = {"actors": {"hero_1": {"ac": 20, "hp": {"current": 12}, "effects": []}}}
        report = execute_task(document, state, roller=FixedDiceRoller([5]))
        self.assertEqual("success", report.status)
        self.assertEqual("skipped", report.step_reports[1].status)
        self.assertEqual(12, state["actors"]["hero_1"]["hp"]["current"])

    def test_invalid_field_map_key_is_rejected(self) -> None:
        document = {
            "task_id": "bad_field_map",
            "version": 1,
            "steps": [
                {
                    "id": "select_targets",
                    "type": "select",
                    "kind": "area",
                    "args": {
                        "shape": "sphere",
                        "radius": 20,
                        "origin": {"x": 0, "y": 0},
                        "field_map": {"position.z": "space.grid.depth"},
                    },
                }
            ],
        }
        with self.assertRaises(ValidationError):
            validate_task_document(document)

    def test_non_string_path_template_is_rejected(self) -> None:
        document = {
            "task_id": "bad_path_template",
            "version": 1,
            "steps": [
                {
                    "id": "attack",
                    "type": "check",
                    "kind": "attack",
                    "tags": ["nat"],
                    "args": {
                        "dice": "1d20",
                        "target_id": "hero_1",
                        "modifier": 3,
                        "target_ac_path_template": 123,
                    },
                }
            ],
        }
        with self.assertRaises(ValidationError):
            validate_task_document(document)


if __name__ == "__main__":
    unittest.main()
