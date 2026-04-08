from __future__ import annotations

import unittest
from pathlib import Path

from augury import create_planner
from augury.agent import PlannerRequest
from augury.agent.models import AskResponse
from augury.agent.runtime import PlannerDependencies
from augury.agent.state_loader import load_toml_state
from augury.agent.tools.search_stub import create_search_stub_tool
from augury.engine.core.dice import FixedDiceRoller


FIXTURE_STATE = Path("examples/evals/planner_e2e/world_state.toml")


class AgentRuntimeTests(unittest.TestCase):
    def load_state(self) -> dict[str, object]:
        return load_toml_state(FIXTURE_STATE)

    def test_runtime_lists_and_loads_default_subagents(self) -> None:
        planner = create_planner(
            state=self.load_state(),
            dependencies=PlannerDependencies(search_tool=create_search_stub_tool()),
        )

        listed = planner.list_skills_tool.invoke({})
        loaded = planner.load_skills_tool.invoke({"skill_ids": ["context_agent", "resolution_agent"]})

        self.assertEqual("ok", listed["status"])
        self.assertEqual({"context_agent", "resolution_agent"}, {item["id"] for item in listed["items"]})
        self.assertEqual("ok", loaded["status"])
        self.assertEqual([], loaded["missing"])
        self.assertEqual({"context_agent", "resolution_agent"}, {item["id"] for item in loaded["loaded"]})

    def test_planner_returns_ready_for_weapon_attack(self) -> None:
        state = self.load_state()
        planner = create_planner(
            state=state,
            dependencies=PlannerDependencies(search_tool=create_search_stub_tool()),
            roller=FixedDiceRoller([15, 6]),
        )

        result = planner.invoke("Aldera用长剑攻击goblin_1")

        self.assertEqual("ready", result.status)
        self.assertEqual("valid", result.lint_result["status"])
        self.assertEqual("success", result.execution_report["status"])
        self.assertIn("check.attack", [f"{step['type']}.{step['kind']}" for step in result.task_document["steps"]])
        self.assertIn("actors.goblin_1.hp.current", {change["path"] for change in result.state_changes})
        self.assertLess(state["actors"]["goblin_1"]["hp"]["current"], 7)

    def test_planner_returns_needs_human_for_ambiguous_fireball(self) -> None:
        planner = create_planner(
            state=self.load_state(),
            dependencies=PlannerDependencies(search_tool=create_search_stub_tool()),
        )

        result = planner.invoke("Aldera用火球术攻击goblin")

        self.assertEqual("needs_human", result.status)
        self.assertTrue(result.ask_requests)
        self.assertTrue(result.missing_info)
        self.assertIsNotNone(result.pending_interrupt)
        self.assertTrue(any("目标实体" in item or "爆点" in item for item in result.missing_info))

    def test_planner_can_resume_after_ask_responses(self) -> None:
        planner = create_planner(
            state=self.load_state(),
            dependencies=PlannerDependencies(search_tool=create_search_stub_tool()),
            roller=FixedDiceRoller([15] + [6] * 8),
        )
        request = PlannerRequest(
            instruction="Aldera用火球术攻击goblin",
            state=self.load_state(),
            ask_responses=[
                AskResponse(question_id="target_disambiguation", selected_option_id="goblin_1"),
                AskResponse(question_id="area_point", selected_option_id="use_target_position"),
            ],
        )

        result = planner.invoke(request)

        self.assertEqual("ready", result.status)
        self.assertFalse(result.ask_requests)
        self.assertEqual(2, len(result.ask_responses))
        self.assertIsNone(result.pending_interrupt)
        self.assertEqual("valid", result.lint_result["status"])

    def test_planner_returns_blocked_when_execution_fails(self) -> None:
        state = self.load_state()
        state["actors"]["aldera"]["spell_slots"]["level_3"]["current"] = 0
        planner = create_planner(
            state=state,
            dependencies=PlannerDependencies(search_tool=create_search_stub_tool()),
            roller=FixedDiceRoller([4] * 12),
        )

        result = planner.invoke("Aldera用火球术攻击goblin_1所在位置")

        self.assertEqual("blocked", result.status)
        self.assertEqual("failed", result.execution_report["status"])
        self.assertTrue(any("Insufficient resource" in item for item in result.blocked_reasons))

    def test_planner_accepts_explicit_task_document(self) -> None:
        state = self.load_state()
        planner = create_planner(
            state=state,
            dependencies=PlannerDependencies(search_tool=create_search_stub_tool()),
        )
        request = PlannerRequest(
            instruction="记录Aldera当前AC供下一轮使用",
            state=state,
            task_document={
                "task_id": "planner.manual-record-ac",
                "version": 1,
                "steps": [
                    {
                        "id": "record_ac",
                        "type": "state",
                        "kind": "set",
                        "args": {
                            "path": "planner_memory.aldera.ac_snapshot",
                            "value": 18,
                        },
                    }
                ],
            },
        )

        result = planner.invoke(request)

        self.assertEqual("ready", result.status)
        self.assertEqual("success", result.execution_report["status"])
        self.assertEqual(18, planner.state["planner_memory"]["aldera"]["ac_snapshot"])


if __name__ == "__main__":
    unittest.main()
