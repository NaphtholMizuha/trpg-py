from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from smoke import test_fetch_keys as fetch_keys_main


def run_fetch_keys(*args: str) -> str:
    buffer = io.StringIO()
    with patch("sys.argv", ["test_fetch_keys.py", *args]):
        with redirect_stdout(buffer):
            raise_code = fetch_keys_main.main()
    if raise_code not in (None, 0):
        raise AssertionError(f"fetch_keys script returned unexpected code: {raise_code}")
    return buffer.getvalue()


class FetchKeysScriptTests(unittest.TestCase):
    def test_script_uses_local_default_state_file(self) -> None:
        output = run_fetch_keys("--json")

        payload = json.loads(output)
        self.assertEqual("ok", payload["all"]["status"])
        self.assertIn("actors.goblin_1.hp.current", payload["all"]["items"])
        self.assertEqual("no_match", payload["no_match"]["status"])

    def test_script_cli_args_override_local_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            override_state_path = temp_path / "override_state.json"
            override_state_path.write_text(
                json.dumps({"actors": {"goblin_1": {"hp": {"current": 7}}}}),
                encoding="utf-8",
            )

            output = run_fetch_keys(
                "--state-file",
                str(override_state_path),
                "--prefix",
                "actors.goblin_1",
                "--json",
            )

        payload = json.loads(output)
        self.assertIn("actors.goblin_1.hp.current", payload["all"]["items"])
        self.assertEqual("ok", payload["prefix"]["status"])
        self.assertIn("actors.goblin_1.hp.current", payload["prefix"]["items"])


if __name__ == "__main__":
    unittest.main()
