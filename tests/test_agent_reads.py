from __future__ import annotations

import io
import unittest

from loguru import logger

from trpg_py.agent.tools import create_read_tool, read_paths


class ReadToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.log_output = io.StringIO()
        self.log_handler_id = logger.add(self.log_output, format="{message}")

    def tearDown(self) -> None:
        logger.remove(self.log_handler_id)

    def test_read_paths_returns_values_for_matching_paths(self) -> None:
        state = {"actors": {"aldera": {"id": "aldera", "ac": 18}}}

        result = read_paths(state, ["actors.aldera.id", "actors.aldera.ac"])

        self.assertEqual("ok", result.status)
        self.assertEqual("aldera", result.items[0].value)
        self.assertEqual(18, result.items[1].value)

    def test_read_paths_returns_per_path_no_match_results(self) -> None:
        state = {"actors": {"aldera": {"id": "aldera"}}}

        result = read_paths(state, ["actors.aldera.id", "actors.goblin_1.id"])

        self.assertEqual("ok", result.status)
        self.assertEqual("ok", result.items[0].status)
        self.assertEqual("no_match", result.items[1].status)
        self.assertIn("missing key", result.items[1].error.message)

    def test_read_paths_returns_no_match_when_every_path_is_missing(self) -> None:
        state = {"actors": {"aldera": {"id": "aldera"}}}

        result = read_paths(state, ["actors.goblin_1.id"])

        self.assertEqual("no_match", result.status)
        self.assertEqual("no_match", result.items[0].status)

    def test_read_tool_logs_success_and_no_match(self) -> None:
        state = {"actors": {"aldera": {"id": "aldera"}}}
        tool = create_read_tool(state=state)

        ok_output = tool.invoke({"paths": ["actors.aldera.id"]})
        miss_output = tool.invoke({"paths": ["actors.goblin_1.id"]})

        self.assertEqual("ok", ok_output["status"])
        self.assertEqual("no_match", miss_output["status"])
        self.assertIn("actors.aldera.id", miss_output["suggestions"])
        logs = self.log_output.getvalue()
        self.assertIn("tool_input tool=read paths=1", logs)
        self.assertIn("tool_output tool=read status=ok", logs)
        self.assertIn("tool_output tool=read status=no_match", logs)

    def test_read_tool_returns_error_when_state_provider_fails(self) -> None:
        def broken_state_provider() -> dict[str, object]:
            raise RuntimeError("state unavailable")

        tool = create_read_tool(state_provider=broken_state_provider)

        output = tool.invoke({"paths": ["actors.aldera.id"]})

        self.assertEqual("error", output["status"])
        self.assertEqual("RuntimeError", output["error"]["type"])
        self.assertIn("state unavailable", output["error"]["message"])
