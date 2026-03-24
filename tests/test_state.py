from __future__ import annotations

import unittest

from trpg_py.errors import StatePathError
from trpg_py.store import read as package_read
from trpg_py.store.compat import get_path, set_path
from trpg_py.store.compat import get_path as compat_get_path
from trpg_py.store.core import read as core_read
from trpg_py.store import mod, mods, read, reads, write, writes


class StatePathTests(unittest.TestCase):
    def test_set_path_creates_missing_dict_nodes(self) -> None:
        state = {"actors": {"goblin_1": {"hp": {"current": 7}}}}
        set_path(state, "actors.goblin_1.status.hex.source", "wizard_1")
        self.assertEqual("wizard_1", get_path(state, "actors.goblin_1.status.hex.source"))

    def test_set_path_rejects_out_of_range_list_index(self) -> None:
        state = {"actors": [{"hp": {"current": 7}}]}
        with self.assertRaises(StatePathError):
            set_path(state, "actors.1.hp.current", 0)

    def test_store_compat_module_matches_top_level_helpers(self) -> None:
        state = {"actors": {"goblin_1": {"hp": {"current": 7}}}}
        self.assertEqual(7, compat_get_path(state, "actors.goblin_1.hp.current"))

    def test_store_reads_preserve_requested_order(self) -> None:
        state = {"actors": {"goblin_1": {"hp": {"current": 7}, "ac": 15}}}
        self.assertEqual([15, 7], reads(state, ["actors.goblin_1.ac", "actors.goblin_1.hp.current"]))

    def test_store_writes_apply_multiple_updates(self) -> None:
        state = {"actors": {"goblin_1": {"hp": {"current": 7}, "ac": 15}}}
        writes(
            state,
            [
                ("actors.goblin_1.hp.current", 3),
                {"path": "actors.goblin_1.ac", "value": 12},
            ],
        )
        self.assertEqual(3, read(state, "actors.goblin_1.hp.current"))
        self.assertEqual(12, read(state, "actors.goblin_1.ac"))

    def test_store_mod_and_mods_require_existing_paths(self) -> None:
        state = {"actors": {"goblin_1": {"hp": {"current": 7}, "ac": 15}}}
        mod(state, "actors.goblin_1.hp.current", lambda value: value - 2)
        mods(state, [("actors.goblin_1.ac", lambda value: value - 1)])
        self.assertEqual(5, read(state, "actors.goblin_1.hp.current"))
        self.assertEqual(14, read(state, "actors.goblin_1.ac"))
        with self.assertRaises(StatePathError):
            mod(state, "actors.goblin_1.missing", lambda value: value)

    def test_store_write_matches_legacy_helpers(self) -> None:
        state = {"actors": {"goblin_1": {"hp": {"current": 7}}}}
        write(state, "actors.goblin_1.hp.current", 1)
        self.assertEqual(1, get_path(state, "actors.goblin_1.hp.current"))

    def test_store_package_exports_match_core_exports(self) -> None:
        self.assertIs(package_read, core_read)


if __name__ == "__main__":
    unittest.main()
