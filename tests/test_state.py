from __future__ import annotations

import unittest

from trpg_py.errors import StatePathError
from trpg_py.state import get_path, set_path


class StatePathTests(unittest.TestCase):
    def test_set_path_creates_missing_dict_nodes(self) -> None:
        state = {"actors": {"goblin_1": {"hp": {"current": 7}}}}
        set_path(state, "actors.goblin_1.status.hex.source", "wizard_1")
        self.assertEqual("wizard_1", get_path(state, "actors.goblin_1.status.hex.source"))

    def test_set_path_rejects_out_of_range_list_index(self) -> None:
        state = {"actors": [{"hp": {"current": 7}}]}
        with self.assertRaises(StatePathError):
            set_path(state, "actors.1.hp.current", 0)


if __name__ == "__main__":
    unittest.main()
