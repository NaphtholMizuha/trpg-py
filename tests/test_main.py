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
        self.assertIn("spend_slot [resource.consume] -> success", output)
        self.assertIn("path=actors.wizard_1.resources.spell_slots.3 cost=1 remaining=0", output)
        self.assertIn("targets: goblin_1, goblin_2", output)
        self.assertIn("goblin_1: amount=18 multiplier=1", output)
        self.assertIn("calc: 12 +2 = 14 vs 15", output)
        self.assertIn("8d6 fire: [3, 3, 3, 3, 2, 2, 1, 1] = 18", output)
        self.assertIn("final: floor(18 * 0.5) = 9", output)
        self.assertIn("actors.wizard_1.resources.spell_slots.3: 1 -> 0", output)
        self.assertIn("actors.goblin_1.hp.current: 18 -> 0", output)
        self.assertIn("actors.goblin_2.hp.current: 18 -> 9", output)

    def test_target_out_of_range_summary_shows_failed_select_reason(self) -> None:
        output = run_main("goblin_scimitar_attack_out_of_range")
        self.assertIn("Task: goblin_scimitar_attack_out_of_range", output)
        self.assertIn("Status: failed", output)
        self.assertIn("pick_target [select.target] -> failed", output)
        self.assertIn("reason: target_out_of_range", output)
        self.assertIn("error: Target 'hero_1' is out of range", output)

    def test_empty_area_summary_shows_none_without_failing(self) -> None:
        output = run_main("fireball_empty")
        self.assertIn("Task: fireball_empty", output)
        self.assertIn("Status: success", output)
        self.assertIn("select_targets [select.area] -> success", output)
        self.assertIn("spend_slot [resource.consume] -> success", output)
        self.assertIn("targets: (none)", output)
        self.assertIn("dex_save [check.save] -> success", output)
        self.assertIn("  no targets", output)
        self.assertIn("fire_damage [damage.apply] -> success", output)
        self.assertIn("actors.wizard_1.resources.spell_slots.3: 1 -> 0", output)

    def test_healing_word_cap_summary_explains_capped_healing(self) -> None:
        output = run_main("healing_word_cap")
        self.assertIn("Task: healing_word_cap", output)
        self.assertIn("spend_slot [resource.consume] -> success", output)
        self.assertIn("path=actors.cleric_1.resources.spell_slots.1 cost=1 remaining=0", output)
        self.assertIn("apply_heal [heal.apply] -> success", output)
        self.assertIn("patient_1: healed=3 requested=5 max_hp=10 capped=yes", output)
        self.assertIn("actors.cleric_1.resources.spell_slots.1: 1 -> 0", output)
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
        self.assertIn("rolls: [2]", output)
        self.assertIn("calc: 2 +4 = 6 vs 16", output)
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
        self.assertIn("=== Demo: goblin_scimitar_attack_out_of_range ===", output)
        self.assertIn("=== Demo: fireball_empty ===", output)
        self.assertIn("=== Demo: fireball_out_of_range ===", output)
        self.assertIn("=== Demo: lightning_bolt_line ===", output)
        self.assertIn("=== Demo: burning_hands_cone ===", output)
        self.assertIn("Overall Summary:", output)
        self.assertIn("- total demos: 12", output)
        self.assertIn("- failed: 3", output)
        self.assertIn("- overall status: failed", output)


if __name__ == "__main__":
    unittest.main()
