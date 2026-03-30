from __future__ import annotations

import unittest

from augury import FixedDiceRoller, execute_task


class CheckOperationTests(unittest.TestCase):
    def test_attack_nat_20_returns_crit_success(self) -> None:
        document = {
            "task_id": "attack_crit",
            "version": 1,
            "steps": [
                {
                    "id": "attack",
                    "type": "check",
                    "kind": "attack",
                    "tags": ["nat"],
                    "args": {"dice": "1d20", "modifier": 5, "target_id": "hero_1", "target_ac": 99},
                }
            ],
        }
        state = {"actors": {"hero_1": {"ac": 99, "hp": {"current": 20}, "effects": []}}}
        report = execute_task(document, state, roller=FixedDiceRoller([20]))
        self.assertEqual("crit_success", report.results["attack"]["outcome"])

    def test_save_nat_20_does_not_auto_succeed(self) -> None:
        document = {
            "task_id": "save_nat20",
            "version": 1,
            "steps": [
                {
                    "id": "save",
                    "type": "check",
                    "kind": "save",
                    "tags": ["nat"],
                    "args": {"dice": "1d20", "ability": "dex", "targets": ["hero_1"], "dc": 25},
                }
            ],
        }
        state = {"actors": {"hero_1": {"saves": {"dex": 0}, "hp": {"current": 20}, "effects": []}}}
        report = execute_task(document, state, roller=FixedDiceRoller([20]))
        self.assertEqual("fail", report.results["save"]["outcome"])

    def test_save_nat_1_does_not_auto_fail(self) -> None:
        document = {
            "task_id": "save_nat1",
            "version": 1,
            "steps": [
                {
                    "id": "save",
                    "type": "check",
                    "kind": "save",
                    "tags": ["nat"],
                    "args": {"dice": "1d20", "ability": "dex", "targets": ["hero_1"], "dc": 10},
                }
            ],
        }
        state = {"actors": {"hero_1": {"saves": {"dex": 9}, "hp": {"current": 20}, "effects": []}}}
        report = execute_task(document, state, roller=FixedDiceRoller([1]))
        self.assertEqual("success", report.results["save"]["outcome"])

    def test_attack_nat_1_returns_crit_fail(self) -> None:
        document = {
            "task_id": "attack_fumble",
            "version": 1,
            "steps": [
                {
                    "id": "attack",
                    "type": "check",
                    "kind": "attack",
                    "tags": ["nat"],
                    "args": {"dice": "1d20", "modifier": 9, "target_id": "hero_1", "target_ac": 5},
                }
            ],
        }
        state = {"actors": {"hero_1": {"ac": 5, "hp": {"current": 20}, "effects": []}}}
        report = execute_task(document, state, roller=FixedDiceRoller([1]))
        self.assertEqual("crit_fail", report.results["attack"]["outcome"])
        self.assertTrue(report.results["attack"]["auto_miss"])

    def test_advantage_chooses_higher_roll(self) -> None:
        document = {
            "task_id": "advantage_attack",
            "version": 1,
            "steps": [
                {
                    "id": "attack",
                    "type": "check",
                    "kind": "attack",
                    "tags": ["nat", "adv"],
                    "args": {"dice": "1d20", "modifier": 2, "target_id": "hero_1", "target_ac": 18},
                }
            ],
        }
        state = {"actors": {"hero_1": {"ac": 18, "hp": {"current": 20}, "effects": []}}}
        report = execute_task(document, state, roller=FixedDiceRoller([5, 17]))
        self.assertEqual("advantage", report.results["attack"]["roll_mode"])
        self.assertEqual([5, 17], report.results["attack"]["rolls"])
        self.assertEqual(17, report.results["attack"]["natural"])
        self.assertEqual("success", report.results["attack"]["outcome"])

    def test_disadvantage_chooses_lower_roll(self) -> None:
        document = {
            "task_id": "disadvantage_attack",
            "version": 1,
            "steps": [
                {
                    "id": "attack",
                    "type": "check",
                    "kind": "attack",
                    "tags": ["nat", "disadv"],
                    "args": {"dice": "1d20", "modifier": 5, "target_id": "hero_1", "target_ac": 10},
                }
            ],
        }
        state = {"actors": {"hero_1": {"ac": 10, "hp": {"current": 20}, "effects": []}}}
        report = execute_task(document, state, roller=FixedDiceRoller([18, 4]))
        self.assertEqual("disadvantage", report.results["attack"]["roll_mode"])
        self.assertEqual([18, 4], report.results["attack"]["rolls"])
        self.assertEqual(4, report.results["attack"]["natural"])
        self.assertEqual(9, report.results["attack"]["total"])

    def test_advantage_and_disadvantage_cancel_to_normal(self) -> None:
        document = {
            "task_id": "normal_mode",
            "version": 1,
            "steps": [
                {
                    "id": "attack",
                    "type": "check",
                    "kind": "attack",
                    "tags": ["nat", "adv", "disadv"],
                    "args": {"dice": "1d20", "modifier": 1, "target_id": "hero_1", "target_ac": 10},
                }
            ],
        }
        state = {"actors": {"hero_1": {"ac": 10, "hp": {"current": 20}, "effects": []}}}
        report = execute_task(document, state, roller=FixedDiceRoller([9]))
        self.assertEqual("normal", report.results["attack"]["roll_mode"])
        self.assertEqual([9], report.results["attack"]["rolls"])

    def test_ability_nat_20_does_not_auto_succeed(self) -> None:
        document = {
            "task_id": "ability_nat20",
            "version": 1,
            "steps": [
                {
                    "id": "check",
                    "type": "check",
                    "kind": "ability",
                    "tags": ["nat"],
                    "args": {"dice": "1d20", "ability": "str", "target_id": "hero_1", "dc": 25},
                }
            ],
        }
        state = {"actors": {"hero_1": {"abilities": {"str": {"modifier": 0}}, "hp": {"current": 20}}}}
        report = execute_task(document, state, roller=FixedDiceRoller([20]))
        self.assertEqual("fail", report.results["check"]["outcome"])

    def test_skill_nat_20_does_not_auto_succeed(self) -> None:
        document = {
            "task_id": "skill_nat20",
            "version": 1,
            "steps": [
                {
                    "id": "check",
                    "type": "check",
                    "kind": "skill",
                    "tags": ["nat"],
                    "args": {"dice": "1d20", "skill": "stealth", "target_id": "hero_1", "dc": 25},
                }
            ],
        }
        state = {"actors": {"hero_1": {"skills": {"stealth": 0}, "hp": {"current": 20}}}}
        report = execute_task(document, state, roller=FixedDiceRoller([20]))
        self.assertEqual("fail", report.results["check"]["outcome"])

    def test_attack_can_read_custom_ac_and_modifier_paths(self) -> None:
        document = {
            "task_id": "custom_attack_paths",
            "version": 1,
            "steps": [
                {
                    "id": "attack",
                    "type": "check",
                    "kind": "attack",
                    "tags": ["nat"],
                    "args": {
                        "dice": "1d20",
                        "target_id": "target_1",
                        "modifier_path": "combatants.attacker_1.offense.attack_bonus",
                        "target_ac_path_template": "combatants.{target_id}.defense.armor_class",
                    },
                }
            ],
        }
        state = {
            "combatants": {
                "attacker_1": {"offense": {"attack_bonus": 5}},
                "target_1": {"defense": {"armor_class": 16}},
            }
        }
        report = execute_task(document, state, roller=FixedDiceRoller([12]))
        self.assertEqual("success", report.status)
        self.assertEqual(17, report.results["attack"]["total"])
        self.assertEqual(16, report.results["attack"]["threshold"])


if __name__ == "__main__":
    unittest.main()
