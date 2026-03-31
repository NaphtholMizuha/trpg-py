from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from smoke import test_grep, test_linter, test_reads, test_search


class FakeSearcher:
    def search(self, query: str, *, limit: int, fetch_k: int) -> SimpleNamespace:
        return SimpleNamespace(
            model_dump=lambda exclude_none=True: {
                "status": "ok",
                "hits": [
                    {
                        "rank": 1,
                        "score": 0.91,
                        "text": f"rule snippet for {query}",
                        "metadata": {"title": "Fireball", "file": "phb"},
                    }
                ],
            }
        )


def run_search_script(*args: str) -> dict[str, object]:
    buffer = io.StringIO()
    with patch("smoke.test_search.build_default_searcher", return_value=FakeSearcher()):
        with patch("sys.argv", ["test_search.py", *args]):
            with redirect_stdout(buffer):
                raise_code = test_search.main()
    if raise_code not in (None, 0):
        raise AssertionError(f"search smoke script returned unexpected code: {raise_code}")
    return json.loads(buffer.getvalue())


def run_linter_script(*args: str) -> tuple[str, dict[str, object]]:
    buffer = io.StringIO()
    payload: dict[str, object] = {}
    with patch("sys.argv", ["test_linter.py", *args]):
        with redirect_stdout(buffer):
            raise_code = test_linter.main()
    if raise_code not in (None, 0):
        raise AssertionError(f"linter smoke script returned unexpected code: {raise_code}")
    if "--json" in args:
        payload = json.loads(buffer.getvalue())
    return buffer.getvalue(), payload


def run_reads_script(*args: str) -> tuple[str, dict[str, object]]:
    buffer = io.StringIO()
    payload: dict[str, object] = {}
    with patch("sys.argv", ["test_reads.py", *args]):
        with redirect_stdout(buffer):
            raise_code = test_reads.main()
    if raise_code not in (None, 0):
        raise AssertionError(f"reads smoke script returned unexpected code: {raise_code}")
    if "--json" in args:
        payload = json.loads(buffer.getvalue())
    return buffer.getvalue(), payload


def run_grep_script(*args: str) -> tuple[str, dict[str, object]]:
    buffer = io.StringIO()
    payload: dict[str, object] = {}
    with patch("sys.argv", ["test_grep.py", *args]):
        with redirect_stdout(buffer):
            raise_code = test_grep.main()
    if raise_code not in (None, 0):
        raise AssertionError(f"grep smoke script returned unexpected code: {raise_code}")
    if "--json" in args:
        payload = json.loads(buffer.getvalue())
    return buffer.getvalue(), payload


class SmokeSearchScriptTests(unittest.TestCase):
    def test_search_smoke_script_supports_json_output(self) -> None:
        payload = run_search_script("--json", "fireball spell")

        self.assertEqual("ok", payload["status"])
        self.assertEqual("Fireball", payload["hits"][0]["metadata"]["title"])


class SmokeLinterScriptTests(unittest.TestCase):
    def test_linter_smoke_script_supports_json_output(self) -> None:
        _, payload = run_linter_script("--json")

        self.assertEqual("valid", payload["valid"]["status"])
        self.assertEqual("invalid", payload["invalid"]["status"])
        self.assertIn("steps.0.id", [issue["path"] for issue in payload["invalid"]["issues"]])

    def test_linter_smoke_script_prints_human_summary(self) -> None:
        output, _ = run_linter_script()

        self.assertIn("TRPG Agent Lint Smoke Test", output)
        self.assertIn("valid demo :", output)
        self.assertIn("invalid demo:", output)
        self.assertIn("status     : valid", output)
        self.assertIn("status     : invalid", output)


class SmokeReadsScriptTests(unittest.TestCase):
    def test_reads_smoke_script_supports_json_output(self) -> None:
        _, payload = run_reads_script("--json")

        self.assertEqual("ok", payload["match"]["status"])
        self.assertEqual("no_match", payload["no_match"]["status"])
        self.assertEqual("aldera", payload["match"]["items"][0]["value"])
        self.assertTrue(payload["no_match"]["suggestions"])

    def test_reads_smoke_script_prints_human_summary(self) -> None:
        output, _ = run_reads_script()

        self.assertIn("TRPG Agent Read Smoke Test", output)
        self.assertIn("match demo :", output)
        self.assertIn("no_match demo:", output)
        self.assertIn("status     : ok", output)
        self.assertIn("status     : no_match", output)
        self.assertIn("suggestions:", output)


class SmokeGrepScriptTests(unittest.TestCase):
    def test_grep_smoke_script_supports_json_output(self) -> None:
        _, payload = run_grep_script("--json")

        self.assertEqual("ok", payload["match"]["status"])
        self.assertEqual("no_match", payload["no_match"]["status"])
        self.assertTrue(payload["match"]["matches"])

    def test_grep_smoke_script_prints_human_summary(self) -> None:
        output, _ = run_grep_script()

        self.assertIn("TRPG Agent Grep Smoke Test", output)
        self.assertIn("match demo :", output)
        self.assertIn("status     : ok", output)
        self.assertIn("status     : no_match", output)
