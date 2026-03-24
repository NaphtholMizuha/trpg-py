from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import main as demo_main


def run_main(*args: str) -> str:
    buffer = io.StringIO()
    with patch("sys.argv", ["main.py", *args]):
        with redirect_stdout(buffer):
            demo_main.main()
    return buffer.getvalue()


class MainIntegrationTests(unittest.TestCase):
    def test_fireball_summary_highlights_targets_and_damage_changes(self) -> None:
        output = run_main("fireball")
        self.assertIn("Task: fireball", output)
        self.assertIn("Status: success", output)
        self.assertIn("select_targets [select.area] -> success", output)
        self.assertIn("targets: goblin_1, goblin_2", output)
        self.assertIn("goblin_1: amount=18 multiplier=1", output)
        self.assertIn("actors.goblin_1.hp.current: 18 -> 0", output)
        self.assertIn("actors.goblin_2.hp.current: 18 -> 9", output)

    def test_healing_word_cap_summary_explains_capped_healing(self) -> None:
        output = run_main("healing_word_cap")
        self.assertIn("Task: healing_word_cap", output)
        self.assertIn("apply_heal [heal.apply] -> success", output)
        self.assertIn("patient_1: healed=3 requested=5 max_hp=10 capped=yes", output)
        self.assertIn("actors.patient_1.hp.current: 7 -> 10", output)

    def test_resource_failure_summary_shows_error_and_no_state_change(self) -> None:
        output = run_main("insufficient_spell_slot")
        self.assertIn("Task: insufficient_spell_slot", output)
        self.assertIn("Status: failed", output)
        self.assertIn("spend_slot [resource.consume] -> failed", output)
        self.assertIn("error: Insufficient resource", output)
        self.assertIn("Applied Changes:\n- (none)", output)

    def test_skipped_step_summary_marks_later_damage_as_skipped(self) -> None:
        output = run_main("goblin_scimitar_attack_miss")
        self.assertIn("Task: goblin_scimitar_attack_miss", output)
        self.assertIn("attack_roll [check.attack] -> success", output)
        self.assertIn("apply_damage [damage.apply] -> skipped", output)
        self.assertIn("Applied Changes:\n- (none)", output)

    def test_custom_layout_summary_uses_real_written_paths(self) -> None:
        output = run_main("custom_layout_fireburst")
        self.assertIn("Task: custom_layout_fireburst", output)
        self.assertIn("select_targets [select.area] -> success", output)
        self.assertIn("combatants.goblin_custom_1.tracks.health.value: 18 -> 0", output)
        self.assertIn("combatants.goblin_custom_2.status_lists.active_effects", output)

    def test_all_mode_runs_registered_demos_in_stable_order(self) -> None:
        output = run_main("all")
        self.assertLess(output.index("=== Demo: goblin_scimitar_attack ==="), output.index("=== Demo: fireball ==="))
        self.assertIn("=== Demo: goblin_scimitar_attack_miss ===", output)
        self.assertIn("=== Demo: lightning_bolt_line ===", output)
        self.assertIn("=== Demo: burning_hands_cone ===", output)
        self.assertIn("Overall Summary:", output)
        self.assertIn("- total demos: 9", output)
        self.assertIn("- failed: 1", output)
        self.assertIn("- overall status: failed", output)


if __name__ == "__main__":
    unittest.main()
