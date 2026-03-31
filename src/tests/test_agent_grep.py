from __future__ import annotations

import io
import sys
import unittest

from loguru import logger

sys.path.insert(0, "src")

from augury.agent.planner_runtime_guards import activate_planner_runtime_guard
from augury.agent.tools import create_grep_tool, grep_lines


class GrepToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.log_output = io.StringIO()
        self.log_handler_id = logger.add(self.log_output, format="{message}")

    def tearDown(self) -> None:
        logger.remove(self.log_handler_id)

    def test_grep_lines_returns_flattened_state_lines(self) -> None:
        state = {
            "actors": {
                "aldera": {"ac": 18, "hp": {"current": 24}},
                "goblin_1": {"attacks": {"scimitar": {"to_hit": 4}}},
            }
        }

        result = grep_lines(state, expressions=["goblin && scimitar && to_hit"])

        self.assertTrue(result)
        self.assertEqual("actors.goblin_1.attacks.scimitar.to_hit = 4", result[0])

    def test_grep_tool_supports_boolean_expression_and_synonyms(self) -> None:
        state = {"actors": {"aldera": {"ac": 18, "hp": {"current": 24}}}}
        tool = create_grep_tool(state=state)

        output = tool.invoke({"expressions": ['aldera && "armor class"']})

        self.assertEqual("ok", output["status"])
        self.assertEqual("actors.aldera.ac = 18", output["matches"][0])
        logs = self.log_output.getvalue()
        self.assertIn("tool_input tool=grep", logs)
        self.assertIn("tool_output tool=grep status=ok", logs)

    def test_grep_tool_supports_multiple_expressions(self) -> None:
        state = {
            "actors": {
                "aldera": {"ac": 18},
                "malik": {"spell_slots": {"1": 4}},
            }
        }
        tool = create_grep_tool(state=state)

        output = tool.invoke({"expressions": ["aldera && ac", "malik && slot"]})

        self.assertEqual("ok", output["status"])
        self.assertEqual(
            {"actors.aldera.ac = 18", "actors.malik.spell_slots.1 = 4"},
            set(output["matches"]),
        )

    def test_grep_tool_preserves_nested_boolean_boundaries(self) -> None:
        state = {
            "actors": {
                "aldera": {"ac": 18},
                "malik": {"spell_slots": {"1": 4}},
                "goblin_1": {"hp": 7},
            }
        }

        result = grep_lines(
            state,
            expressions=["((malik && slot) || (aldera && ac))"],
        )

        self.assertEqual(
            {"actors.aldera.ac = 18", "actors.malik.spell_slots.1 = 4"},
            set(result),
        )
        self.assertNotIn("actors.goblin_1.hp = 7", set(result))

    def test_grep_tool_returns_no_match_when_no_line_matches(self) -> None:
        tool = create_grep_tool(state={"actors": {"aldera": {"ac": 18}}})

        output = tool.invoke({"expressions": ["spell && slot"]})

        self.assertEqual("no_match", output["status"])
        self.assertEqual([], output["matches"])
        self.assertNotIn("error", output)
        logs = self.log_output.getvalue()
        self.assertIn("tool_output tool=grep status=no_match matches=0", logs)

    def test_grep_tool_short_circuits_repeated_theme_with_runtime_guard(self) -> None:
        tool = create_grep_tool(
            state={"actors": {"goblin_1": {"attacks": {"scimitar": {"to_hit": 4}}}}}
        )

        request = {"expressions": ["goblin && to_hit"]}
        with activate_planner_runtime_guard():
            first = tool.invoke(request)
            second = tool.invoke(request)

        self.assertEqual(first, second)
        logs = self.log_output.getvalue()
        self.assertIn("tool_guard tool=grep kind=repeated_theme", logs)

    def test_grep_tool_returns_error_when_state_provider_fails(self) -> None:
        def broken_state_provider() -> dict[str, object]:
            raise RuntimeError("state unavailable")

        tool = create_grep_tool(state_provider=broken_state_provider)

        output = tool.invoke({"expressions": ["ac"]})

        self.assertEqual("error", output["status"])
        self.assertEqual("RuntimeError", output["error"]["type"])
        self.assertIn("state unavailable", output["error"]["message"])


if __name__ == "__main__":
    unittest.main()
