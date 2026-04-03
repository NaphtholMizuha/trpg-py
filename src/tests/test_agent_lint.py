from __future__ import annotations

import unittest
from unittest.mock import patch

from augury.planner.tools import create_lint_tool, lint_task_document


class LintToolTests(unittest.TestCase):
    def test_lint_task_document_returns_valid_for_executable_document(self) -> None:
        document = {
            "task_id": "goblin_scimitar_attack",
            "version": 1,
            "policy": {"ruleset": "dnd5e-2014"},
            "context": {"target_id": "hero_1"},
            "steps": [
                {
                    "id": "attack_roll",
                    "type": "check",
                    "kind": "attack",
                    "tags": ["nat"],
                    "args": {
                        "dice": "1d20",
                        "modifier": 4,
                        "target_id": {"$ref": "context.target_id"},
                        "target_ac": 16,
                    },
                }
            ],
        }

        result = lint_task_document(document)

        self.assertEqual("valid", result.status)
        self.assertEqual("TaskDocument is valid.", result.summary)
        self.assertEqual([], result.issues)

    def test_lint_task_document_reports_missing_fields_with_paths(self) -> None:
        document = {
            "task_id": "broken",
            "version": 1,
            "steps": [{"action": "attack"}],
        }

        result = lint_task_document(document)

        self.assertEqual("invalid", result.status)
        self.assertIn("validation errors for TaskDocumentSchema", result.summary)
        self.assertIn("steps.0.id", [issue.path for issue in result.issues])
        self.assertIn("steps.0.type", [issue.path for issue in result.issues])
        self.assertIn("steps.0.kind", [issue.path for issue in result.issues])
        self.assertIn("steps.0.args", [issue.path for issue in result.issues])

    def test_lint_task_document_reports_semantic_validation_failures(self) -> None:
        document = {
            "task_id": "bad-tags",
            "version": 1,
            "steps": [
                {
                    "id": "attack_roll",
                    "type": "check",
                    "kind": "attack",
                    "tags": ["oops"],
                    "args": {"dice": "1d20", "target_id": "hero_1", "target_ac": 16},
                }
            ],
        }

        result = lint_task_document(document)

        self.assertEqual("invalid", result.status)
        self.assertIn("unsupported check tags", result.summary)
        self.assertEqual("steps.0", result.issues[0].path)
        self.assertEqual("check", result.issues[0].expected["step_type"])
        self.assertEqual("attack", result.issues[0].expected["step_kind"])
        self.assertIn("dice", result.issues[0].expected["required_args"])

    def test_lint_task_document_reports_multiple_independent_semantic_failures(self) -> None:
        document = {
            "task_id": "many-problems",
            "version": 1,
            "steps": [
                {
                    "id": "attack_roll",
                    "type": "check",
                    "kind": "attack",
                    "tags": ["oops"],
                    "args": {"dice": "1d20", "target_id": "hero_1", "target_ac": 16},
                },
                {
                    "id": "select_area",
                    "type": "select",
                    "kind": "area",
                    "args": {"shape": "sphere", "radius": 20},
                },
                {
                    "id": "use_slot",
                    "type": "resource",
                    "kind": "consume",
                    "args": {},
                },
            ],
        }

        result = lint_task_document(document)

        self.assertEqual("invalid", result.status)
        self.assertGreaterEqual(len(result.issues), 3)
        issue_paths = {issue.path for issue in result.issues}
        self.assertIn("steps.0", issue_paths)
        self.assertIn("steps.1", issue_paths)
        self.assertIn("steps.2", issue_paths)
        self.assertIn("unsupported check tags", result.summary)
        self.assertIn("must define shape and origin", result.summary)
        self.assertIn("must define a path", result.summary)

        expected_by_path = {issue.path: issue.expected for issue in result.issues}
        self.assertEqual("attack", expected_by_path["steps.0"]["step_kind"])
        self.assertEqual("area", expected_by_path["steps.1"]["step_kind"])
        self.assertEqual("consume", expected_by_path["steps.2"]["step_kind"])

    def test_lint_task_document_returns_template_guidance_for_check_save(self) -> None:
        document = {
            "task_id": "bad-save",
            "version": 1,
            "steps": [
                {
                    "id": "dexterity_save",
                    "type": "check",
                    "kind": "save",
                    "args": {"save_ability": "dexterity", "dc_path": "state.actors.aldera.spell_dc"},
                }
            ],
        }

        result = lint_task_document(document)

        self.assertEqual("invalid", result.status)
        issue = result.issues[0]
        self.assertEqual("steps.0", issue.path)
        self.assertEqual("check", issue.expected["step_type"])
        self.assertEqual("save", issue.expected["step_kind"])
        self.assertIn("dice", issue.expected["required_args"])
        self.assertIn(["dc", "dc_path"], issue.expected["one_of_required"])
        self.assertIn("ability", issue.expected["allowed_args"])
        self.assertIn("Use ability, not save_ability.", issue.expected["common_mistakes"])
        self.assertEqual("1d20", issue.expected["canonical_example"]["args"]["dice"])

    def test_lint_tool_reports_tool_errors_separately(self) -> None:
        tool = create_lint_tool()

        with patch("augury.planner.tools.lint.lint_task_document", side_effect=RuntimeError("lint backend failed")):
            payload = tool.invoke(
                {
                    "task_document": {
                        "task_id": "demo",
                        "version": 1,
                        "steps": [],
                    }
                }
            )

        self.assertEqual("error", payload["status"])
        self.assertEqual("RuntimeError", payload["error"]["type"])
        self.assertIn("lint backend failed", payload["error"]["message"])
