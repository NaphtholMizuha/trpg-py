from __future__ import annotations

import io
import unittest

from loguru import logger

from trpg_py.agent.tools import create_list_tool


class ListToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.log_output = io.StringIO()
        self.log_handler_id = logger.add(self.log_output, format="{message}")

    def tearDown(self) -> None:
        logger.remove(self.log_handler_id)

    def test_list_returns_all_paths(self) -> None:
        state = {"actors": {"goblin_1": {"hp": {"current": 7}}, "hero_1": {"ac": 16}}}
        tool = create_list_tool(state=state)

        output = tool.invoke({})

        self.assertEqual("ok", output["status"])
        self.assertEqual(
            ["actors.goblin_1.hp.current", "actors.hero_1.ac"],
            output["items"],
        )
        logs = self.log_output.getvalue()
        self.assertIn("tool_input tool=list prefix=None", logs)
        self.assertIn("tool_output tool=list status=ok items=2", logs)

    def test_list_supports_prefix_filter(self) -> None:
        state = {"actors": {"goblin_1": {"hp": {"current": 7}, "ac": 13}, "hero_1": {"ac": 16}}}
        tool = create_list_tool(state=state)

        output = tool.invoke({"prefix": "actors.goblin_1"})

        self.assertEqual("ok", output["status"])
        self.assertEqual(
            ["actors.goblin_1.ac", "actors.goblin_1.hp.current"],
            output["items"],
        )

    def test_list_returns_no_match_for_empty_prefix_results(self) -> None:
        tool = create_list_tool(state={"actors": {"hero_1": {"ac": 16}}})

        output = tool.invoke({"prefix": "actors.goblin_1"})

        self.assertEqual("no_match", output["status"])
        self.assertEqual([], output["items"])
        self.assertIn("actors.hero_1.ac", output["suggestions"])
        self.assertNotIn("error", output)
        logs = self.log_output.getvalue()
        self.assertIn("tool_output tool=list status=no_match items=0 suggestions=", logs)

    def test_list_returns_error_when_state_provider_fails(self) -> None:
        def broken_state_provider() -> dict[str, object]:
            raise RuntimeError("state unavailable")

        tool = create_list_tool(state_provider=broken_state_provider)

        output = tool.invoke({})

        self.assertEqual("error", output["status"])
        self.assertEqual("RuntimeError", output["error"]["type"])
        self.assertIn("state unavailable", output["error"]["message"])
        logs = self.log_output.getvalue()
        self.assertIn("tool_output tool=list status=error", logs)
        self.assertIn("error_type=RuntimeError", logs)


if __name__ == "__main__":
    unittest.main()
