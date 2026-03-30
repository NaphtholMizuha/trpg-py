from __future__ import annotations

import unittest
from unittest.mock import patch

from augury.agent.tools import create_lint_tool, lint_task_document


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
        self.assertEqual("", result.issues[0].path)

    def test_lint_tool_reports_tool_errors_separately(self) -> None:
        tool = create_lint_tool()

        with patch("augury.agent.tools.lint.lint_task_document", side_effect=RuntimeError("lint backend failed")):
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
