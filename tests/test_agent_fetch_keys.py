from __future__ import annotations

import unittest

from trpg_py.agent.tools import create_fetch_keys_tool


class FetchKeysToolTests(unittest.TestCase):
    def test_fetch_keys_returns_all_paths(self) -> None:
        state = {"actors": {"goblin_1": {"hp": {"current": 7}}, "hero_1": {"ac": 16}}}
        tool = create_fetch_keys_tool(state=state)

        output = tool.invoke({})

        self.assertEqual("ok", output["status"])
        self.assertEqual(
            ["actors.goblin_1.hp.current", "actors.hero_1.ac"],
            output["items"],
        )

    def test_fetch_keys_supports_prefix_filter(self) -> None:
        state = {"actors": {"goblin_1": {"hp": {"current": 7}, "ac": 13}, "hero_1": {"ac": 16}}}
        tool = create_fetch_keys_tool(state=state)

        output = tool.invoke({"prefix": "actors.goblin_1"})

        self.assertEqual("ok", output["status"])
        self.assertEqual(
            ["actors.goblin_1.ac", "actors.goblin_1.hp.current"],
            output["items"],
        )

    def test_fetch_keys_returns_no_match_for_empty_prefix_results(self) -> None:
        tool = create_fetch_keys_tool(state={"actors": {"hero_1": {"ac": 16}}})

        output = tool.invoke({"prefix": "actors.goblin_1"})

        self.assertEqual("no_match", output["status"])
        self.assertEqual([], output["items"])
        self.assertNotIn("error", output)

    def test_fetch_keys_returns_error_when_state_provider_fails(self) -> None:
        def broken_state_provider() -> dict[str, object]:
            raise RuntimeError("state unavailable")

        tool = create_fetch_keys_tool(state_provider=broken_state_provider)

        output = tool.invoke({})

        self.assertEqual("error", output["status"])
        self.assertEqual("RuntimeError", output["error"]["type"])
        self.assertIn("state unavailable", output["error"]["message"])


if __name__ == "__main__":
    unittest.main()
