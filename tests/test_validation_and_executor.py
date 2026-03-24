from __future__ import annotations

import unittest

from trpg_py import FixedDiceRoller, execute_task, validate_task_document
from trpg_py.engine import execute_task as engine_execute_task
from trpg_py.engine import validate_task_document as engine_validate_task_document
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

    def test_targeting_requires_required_keys(self) -> None:
        document = {
            "task_id": "bad_targeting",
            "version": 1,
            "steps": [
                {
                    "id": "pick_target",
                    "type": "select",
                    "kind": "target",
                    "args": {
                        "source": "hero_1",
                        "targeting": {
                            "source_position": {"x": 0, "y": 0},
                            "max_range": 5,
                        },
                    },
                }
            ],
        }
        with self.assertRaises(ValidationError):
            validate_task_document(document)

    def test_targeting_accepts_ref_based_source_position(self) -> None:
        document = {
            "task_id": "targeting_ref",
            "version": 1,
            "context": {"origin": {"x": 0, "y": 0}},
            "steps": [
                {
                    "id": "pick_area",
                    "type": "select",
                    "kind": "area",
                    "args": {
                        "shape": "sphere",
                        "origin": {"$ref": "context.origin"},
                        "radius": 20,
                        "targeting": {
                            "source_position": {"$ref": "context.origin"},
                            "max_range": 150,
                            "range_metric": "euclidean",
                        },
                    },
                }
            ],
        }
        task = validate_task_document(document)
        self.assertEqual("pick_area", task.steps[0].id)

    def test_engine_namespace_re_exports_executor_entrypoints(self) -> None:
        self.assertIs(engine_execute_task, execute_task)
        self.assertIs(engine_validate_task_document, validate_task_document)


if __name__ == "__main__":
    unittest.main()
