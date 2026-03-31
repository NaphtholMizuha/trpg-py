from __future__ import annotations

import io
import unittest

from loguru import logger

from augury.agent.planner_runtime_guards import activate_planner_runtime_guard
from augury.agent.tools import create_grep_tool, grep_leaf_paths


class GrepToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.log_output = io.StringIO()
        self.log_handler_id = logger.add(self.log_output, format="{message}")

    def tearDown(self) -> None:
        logger.remove(self.log_handler_id)

    def test_grep_leaf_paths_returns_ranked_leaf_matches(self) -> None:
        state = {
            "actors": {
                "aldera": {"ac": 18, "hp": {"current": 24}},
                "goblin_1": {"attacks": {"scimitar": {"to_hit": 4}}},
            }
        }

        result = grep_leaf_paths(state, terms=["goblin", "scimitar", "to_hit"])

        self.assertTrue(result)
        self.assertEqual("actors.goblin_1.attacks.scimitar.to_hit", result[0].path)
        self.assertIn("goblin", result[0].matched_terms)
        self.assertIn("scimitar", result[0].matched_terms)

    def test_grep_tool_supports_query_terms_and_synonyms(self) -> None:
        state = {"actors": {"aldera": {"ac": 18, "hp": {"current": 24}}}}
        tool = create_grep_tool(state=state)

        output = tool.invoke({"query": "Aldera armor class"})

        self.assertEqual("ok", output["status"])
        self.assertEqual("actors.aldera.ac", output["matches"][0]["path"])
        self.assertIn("armor", output["matches"][0]["matched_terms"])
        logs = self.log_output.getvalue()
        self.assertIn("tool_input tool=grep", logs)
        self.assertIn("tool_output tool=grep status=ok", logs)

    def test_grep_tool_returns_no_match_when_no_leaf_path_matches(self) -> None:
        tool = create_grep_tool(state={"actors": {"aldera": {"ac": 18}}})

        output = tool.invoke({"terms": ["spell", "slot"]})

        self.assertEqual("no_match", output["status"])
        self.assertEqual([], output["matches"])
        self.assertNotIn("error", output)
        logs = self.log_output.getvalue()
        self.assertIn("tool_output tool=grep status=no_match matches=0", logs)

    def test_grep_tool_short_circuits_repeated_theme_with_runtime_guard(self) -> None:
        tool = create_grep_tool(
            state={"actors": {"goblin_1": {"attacks": {"scimitar": {"to_hit": 4}}}}}
        )

        with activate_planner_runtime_guard():
            first = tool.invoke({"terms": ["goblin", "to_hit"]})
            second = tool.invoke({"terms": ["goblin", "to_hit"]})

        self.assertEqual(first, second)
        logs = self.log_output.getvalue()
        self.assertIn("tool_guard tool=grep kind=repeated_theme", logs)

    def test_grep_tool_returns_error_when_state_provider_fails(self) -> None:
        def broken_state_provider() -> dict[str, object]:
            raise RuntimeError("state unavailable")

        tool = create_grep_tool(state_provider=broken_state_provider)

        output = tool.invoke({"terms": ["ac"]})

        self.assertEqual("error", output["status"])
        self.assertEqual("RuntimeError", output["error"]["type"])
        self.assertIn("state unavailable", output["error"]["message"])


if __name__ == "__main__":
    unittest.main()
