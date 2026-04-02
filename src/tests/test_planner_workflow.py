from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "src")

from augury.planner import PlannerWorkflow, PlannerWorkflowDependencies
from augury.planner.nodes import DslNode, DslNodeDependencies, TaskNode, TaskNodeDependencies
from augury.planner.task_document import TaskDraft
from augury.planner.tools import create_grep_tool, create_lint_tool
from tests.config_helpers import write_project_config


class FakeAgent:
    def __init__(self, payload: object, call_log: list[str], marker: str) -> None:
        self.payload = payload
        self.call_log = call_log
        self.marker = marker

    def invoke(self, state: dict[str, object]) -> dict[str, object]:
        self.call_log.append(self.marker)
        self.call_log.append(state["messages"][0]["content"])  # type: ignore[index]
        return {"structured_response": self.payload}


class RecordingAgentFactory:
    def __init__(self, payload: object, marker: str, call_log: list[str]) -> None:
        self.payload = payload
        self.marker = marker
        self.call_log = call_log
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs: object) -> FakeAgent:
        self.calls.append(kwargs)
        return FakeAgent(self.payload, self.call_log, self.marker)


class PlannerWorkflowTests(unittest.TestCase):
    def test_task_node_prompt_files_define_judgment_first_order(self) -> None:
        system_prompt = Path("config/prompts/planner_task_node_system.txt").read_text(encoding="utf-8")
        user_prompt = Path("config/prompts/planner_task_node_user.txt").read_text(encoding="utf-8")

        self.assertIn("optional search", system_prompt)
        self.assertIn("Write the judgments before you finalize reads or writes", system_prompt)
        self.assertIn("Use the internal order: classify task shape, optional search first, then judgments, then grep", user_prompt)
        self.assertIn("reads, writes, missing_info, and assumptions must be derived from the judgments", user_prompt)

    def test_task_node_prompt_files_require_rule_driven_alignment(self) -> None:
        system_prompt = Path("config/prompts/planner_task_node_system.txt").read_text(encoding="utf-8")
        user_prompt = Path("config/prompts/planner_task_node_user.txt").read_text(encoding="utf-8")

        self.assertIn("If a judgment says a target makes a saving throw", system_prompt)
        self.assertIn("writes should include that exact HP path", system_prompt)
        self.assertIn("If a judgment says a target makes a saving throw, reads should include the target's exact save path", user_prompt)
        self.assertIn("If an actor resource path is confirmed and the instruction consumes it, writes should usually include that resource path", user_prompt)

    def test_task_node_prompt_files_require_evidence_and_states_fields(self) -> None:
        system_prompt = Path("config/prompts/planner_task_node_system.txt").read_text(encoding="utf-8")
        user_prompt = Path("config/prompts/planner_task_node_user.txt").read_text(encoding="utf-8")

        self.assertIn("evidence must contain only short excerpts", system_prompt)
        self.assertIn("states must contain only the key state evidence lines", system_prompt)
        self.assertIn("not a tool log or a full rule quotation", user_prompt)
        self.assertIn("states must contain only short state evidence lines", user_prompt)

    def test_task_node_prompt_files_define_task_shape_prototypes(self) -> None:
        system_prompt = Path("config/prompts/planner_task_node_system.txt").read_text(encoding="utf-8")
        user_prompt = Path("config/prompts/planner_task_node_user.txt").read_text(encoding="utf-8")

        self.assertIn("single-target attack", system_prompt)
        self.assertIn("single-target spell", system_prompt)
        self.assertIn("area spell or area effect", system_prompt)
        self.assertIn("healing or buff", system_prompt)
        self.assertIn("condition or status effect", system_prompt)
        self.assertIn("pure state query", system_prompt)
        self.assertIn("classify the task into a prototype", user_prompt)

    def test_task_node_prompt_files_require_aoe_position_and_slot_binding(self) -> None:
        system_prompt = Path("config/prompts/planner_task_node_system.txt").read_text(encoding="utf-8")
        user_prompt = Path("config/prompts/planner_task_node_user.txt").read_text(encoding="utf-8")

        self.assertIn("If the instruction names a spell, first confirm the spell identity", system_prompt)
        self.assertIn("default to the spell's native level", system_prompt)
        self.assertIn("If coverage depends on actor or target position", system_prompt)
        self.assertIn("bind the spell's native level or explicit upcast level", user_prompt)
        self.assertIn("If an area effect depends on position or distance", user_prompt)
        self.assertIn("add that gap to missing_info", user_prompt)

    def test_task_node_prompt_files_use_non_fireball_few_shot_for_area_spells(self) -> None:
        system_prompt = Path("config/prompts/planner_task_node_system.txt").read_text(encoding="utf-8")
        user_prompt = Path("config/prompts/planner_task_node_user.txt").read_text(encoding="utf-8")

        self.assertIn("Malik用闪电束攻击orc", system_prompt)
        self.assertIn("then grep for `malik && position`", system_prompt)
        self.assertIn("then grep for `orc && position`", system_prompt)
        self.assertNotIn("Aldera用火球术攻击goblin", system_prompt)
        self.assertNotIn("火球术 Fireball", system_prompt)
        self.assertIn("intentionally excludes `火球术 Fireball`", user_prompt)

    def test_task_node_prompt_files_define_search_query_modes(self) -> None:
        system_prompt = Path("config/prompts/planner_task_node_system.txt").read_text(encoding="utf-8")
        user_prompt = Path("config/prompts/planner_task_node_user.txt").read_text(encoding="utf-8")

        self.assertIn("term", system_prompt)
        self.assertIn("balanced", system_prompt)
        self.assertIn("semantic", system_prompt)
        self.assertIn("Use `balanced` when a named rule is known and you need a few concrete resolution details", system_prompt)
        self.assertIn("choose one search mode: `term`, `balanced`, or `semantic`", user_prompt)
        self.assertIn("Use `semantic` only when there is no reliable rule-term anchor", user_prompt)

    def test_workflow_uses_langgraph_and_create_agent_backed_nodes(self) -> None:
        call_log: list[str] = []
        state = {"actors": {"aldera": {"ac": 18}}}
        draft = TaskDraft(
            instruction="Review Aldera AC before the next turn",
            normalized_instruction="Review Aldera AC before the next turn",
            task="Read Aldera's AC and record it back to the tracked state for later resolution.",
            reads=["actors.aldera.ac"],
            judgments=["Use Aldera's AC as the defensive threshold for the later resolution."],
            writes=["actors.aldera.ac"],
            assumptions=[],
            missing_info=[],
            evidence=["Aldera AC is needed as the later defensive threshold."],
            states=["actors.aldera.ac = 18"],
        )
        document = {
            "task_id": "planner.review-aldera-ac",
            "version": 1,
            "policy": {},
            "context": {
                "instruction": draft.instruction,
                "task_draft": draft.model_dump(),
            },
            "steps": [
                {
                    "id": "apply_brief",
                    "type": "state",
                    "kind": "set",
                    "args": {
                        "path": "actors.aldera.ac",
                        "value": {
                            "instruction": draft.instruction,
                            "task": draft.task,
                            "judgments": draft.judgments,
                        },
                    },
                }
            ],
        }
        task_factory = RecordingAgentFactory(draft, "task", call_log)
        dsl_factory = RecordingAgentFactory(document, "dsl", call_log)

        task_node = TaskNode(
            TaskNodeDependencies(
                grep_tool=create_grep_tool(state=state),
                agent_factory=task_factory,
                model="openai:test-planner",
            )
        )
        dsl_node = DslNode(
            DslNodeDependencies(
                lint_tool=create_lint_tool(),
                agent_factory=dsl_factory,
                model="openai:test-planner",
            )
        )
        workflow = PlannerWorkflow(
            state=state,
            dependencies=PlannerWorkflowDependencies(
                task_node=task_node,
                dsl_node=dsl_node,
            ),
        )

        result = workflow.invoke("Review Aldera AC before the next turn")

        self.assertEqual("ready", result.status)
        self.assertEqual("task", call_log[0])
        self.assertEqual("dsl", call_log[2])
        self.assertEqual("valid", result.lint_result["status"])
        self.assertEqual("planner.review-aldera-ac", result.task_document["task_id"])
        self.assertEqual(1, len(task_factory.calls))
        self.assertEqual(1, len(dsl_factory.calls))
        self.assertEqual("planner_task_node", task_factory.calls[0]["name"])
        self.assertEqual("planner_dsl_node", dsl_factory.calls[0]["name"])
        self.assertEqual(1, len(task_factory.calls[0]["tools"]))
        self.assertEqual(1, len(dsl_factory.calls[0]["tools"]))
        self.assertEqual(draft.task, result.draft.task)
        self.assertEqual(["Aldera AC is needed as the later defensive threshold."], result.draft.evidence)
        self.assertEqual(["actors.aldera.ac = 18"], result.draft.states)

    def test_nodes_load_default_prompts_from_config_files(self) -> None:
        call_log: list[str] = []
        draft = TaskDraft(
            instruction="Track Aldera AC",
            normalized_instruction="Track Aldera AC",
            task="Read Aldera AC and carry it into the task document.",
            reads=["actors.aldera.ac"],
            judgments=["Use Aldera AC when evaluating the later resolution."],
            writes=["actors.aldera.ac"],
            assumptions=[],
            missing_info=[],
            evidence=["Aldera AC is the tracked defensive threshold."],
            states=["actors.aldera.ac = 18"],
        )
        document = {
            "task_id": "planner.track-aldera-ac",
            "version": 1,
            "policy": {},
            "context": {"instruction": draft.instruction, "task_draft": draft.model_dump()},
            "steps": [
                {
                    "id": "record_aldera_ac",
                    "type": "state",
                    "kind": "set",
                    "args": {"path": "actors.aldera.ac", "value": 18},
                }
            ],
        }
        task_factory = RecordingAgentFactory(draft, "task", call_log)
        dsl_factory = RecordingAgentFactory(document, "dsl", call_log)

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(
                Path(temp_dir) / "config.toml",
                planner_task_node_system_prompt_template="Task system prompt from file",
                planner_task_node_user_prompt_template='Task user prompt from file: {{instruction}}',
                planner_dsl_node_system_prompt_template="DSL system prompt from file",
                planner_dsl_node_user_prompt_template="DSL user prompt from file: {{task_draft_json}}",
            )
            task_node = TaskNode(
                TaskNodeDependencies(
                    grep_tool=create_grep_tool(state={"actors": {"aldera": {"ac": 18}}}),
                    agent_factory=task_factory,
                    model="openai:test-planner",
                    config_path=config_path,
                )
            )
            dsl_node = DslNode(
                DslNodeDependencies(
                    lint_tool=create_lint_tool(),
                    agent_factory=dsl_factory,
                    model="openai:test-planner",
                    config_path=config_path,
                )
            )

            task_result = task_node.run("Track Aldera AC")
            dsl_result, lint_result = dsl_node.run(task_result)

        self.assertEqual(1, len(task_factory.calls))
        self.assertEqual(1, len(task_factory.calls[0]["tools"]))
        self.assertEqual("Task system prompt from file", task_factory.calls[0]["system_prompt"])
        self.assertEqual("DSL system prompt from file", dsl_factory.calls[0]["system_prompt"])
        self.assertIn("Track Aldera AC", call_log[1])
        self.assertTrue(call_log[1].startswith("Task user prompt from file: "))
        self.assertTrue(call_log[3].startswith("DSL user prompt from file: "))
        self.assertEqual("planner.track-aldera-ac", dsl_result["task_id"])
        self.assertEqual("valid", lint_result["status"])

    def test_explicit_prompts_override_config_file_defaults(self) -> None:
        call_log: list[str] = []
        draft = TaskDraft(
            instruction="Track Malik HP",
            normalized_instruction="Track Malik HP",
            task="Read Malik HP and capture it in the task document.",
            reads=["actors.malik.hp.current"],
            judgments=["Use Malik HP as the tracked value."],
            writes=["actors.malik.hp.current"],
            assumptions=[],
            missing_info=[],
            evidence=["Malik HP is the tracked value for the next step."],
            states=["actors.malik.hp.current = 22"],
        )
        document = {
            "task_id": "planner.track-malik-hp",
            "version": 1,
            "policy": {},
            "context": {"instruction": draft.instruction, "task_draft": draft.model_dump()},
            "steps": [
                {
                    "id": "record_malik_hp",
                    "type": "state",
                    "kind": "set",
                    "args": {"path": "actors.malik.hp.current", "value": 22},
                }
            ],
        }
        task_factory = RecordingAgentFactory(draft, "task", call_log)
        dsl_factory = RecordingAgentFactory(document, "dsl", call_log)

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(
                Path(temp_dir) / "config.toml",
                planner_task_node_system_prompt_template="Task system prompt from file",
                planner_task_node_user_prompt_template='Task user prompt from file: {{instruction}}',
                planner_dsl_node_system_prompt_template="DSL system prompt from file",
                planner_dsl_node_user_prompt_template="DSL user prompt from file: {{task_draft_json}}",
            )
            task_node = TaskNode(
                TaskNodeDependencies(
                    grep_tool=create_grep_tool(state={"actors": {"malik": {"hp": {"current": 22}}}}),
                    agent_factory=task_factory,
                    model="openai:test-planner",
                    config_path=config_path,
                    system_prompt="Task system prompt override",
                    user_prompt_template='Task user prompt override: {{instruction}}',
                )
            )
            dsl_node = DslNode(
                DslNodeDependencies(
                    lint_tool=create_lint_tool(),
                    agent_factory=dsl_factory,
                    model="openai:test-planner",
                    config_path=config_path,
                    system_prompt="DSL system prompt override",
                    user_prompt_template="DSL user prompt override: {{task_draft_json}}",
                )
            )

            task_result = task_node.run("Track Malik HP")
            dsl_result, lint_result = dsl_node.run(task_result)

        self.assertEqual("Task system prompt override", task_factory.calls[0]["system_prompt"])
        self.assertEqual("DSL system prompt override", dsl_factory.calls[0]["system_prompt"])
        self.assertIn("Track Malik HP", call_log[1])
        self.assertTrue(call_log[1].startswith("Task user prompt override: "))
        self.assertTrue(call_log[3].startswith("DSL user prompt override: "))
        self.assertIn('"instruction": "Track Malik HP"', call_log[3])
        self.assertEqual("planner.track-malik-hp", dsl_result["task_id"])
        self.assertEqual("valid", lint_result["status"])

    def test_task_node_passes_available_tools_to_single_agent(self) -> None:
        call_log: list[str] = []
        draft = TaskDraft(
            instruction="Aldera用长剑攻击goblin",
            normalized_instruction="Aldera用长剑攻击goblin",
            task="Resolve Aldera's melee attack against the goblin.",
            reads=["actors.aldera.equipment.main_hand.name", "actors.goblin_1.hp.current"],
            judgments=["Compare the attack total against the goblin's AC."],
            writes=["actors.goblin_1.hp.current"],
            assumptions=[],
            missing_info=[],
            evidence=["Aldera is resolving a melee weapon attack against goblin_1."],
            states=["actors.aldera.equipment.main_hand.name = +1长剑"],
        )
        task_factory = RecordingAgentFactory(draft, "task", call_log)

        class FakeGrepTool:
            name = "grep"

        task_node = TaskNode(
            TaskNodeDependencies(
                grep_tool=FakeGrepTool(),
                agent_factory=task_factory,
                model="openai:test-planner",
                system_prompt="Task system prompt override",
                user_prompt_template="Task user prompt override: {{instruction}}",
            )
        )

        result = task_node.run("Aldera用长剑攻击goblin")

        self.assertEqual(1, len(task_factory.calls))
        self.assertEqual(1, len(task_factory.calls[0]["tools"]))
        self.assertIn("actors.aldera.equipment.main_hand.name = +1长剑", result.states)

    def test_task_node_filters_states_to_relevant_evidence(self) -> None:
        call_log: list[str] = []
        draft = TaskDraft(
            instruction="Aldera用长剑攻击goblin",
            normalized_instruction="Aldera用长剑攻击goblin",
            task="Resolve Aldera's melee attack against the goblin and apply damage to the goblin HP.",
            reads=[
                "actors.aldera.equipment.main_hand.attack_bonus",
                "actors.goblin_1.hp.current",
            ],
            judgments=["Compare the attack total against the goblin AC."],
            writes=["actors.goblin_1.hp.current"],
            assumptions=[],
            missing_info=[],
            evidence=["Attack resolution depends on the goblin HP write."],
            states=[
                "actors.aldera.abilities.cha.modifier = 4",
                "actors.aldera.equipment.main_hand.attack_bonus = 7",
                "actors.goblin_1.hp.current = 7",
                "actors.goblin_1.position.x = 4",
            ],
        )
        task_factory = RecordingAgentFactory(draft, "task", call_log)
        task_node = TaskNode(
            TaskNodeDependencies(
                agent_factory=task_factory,
                model="openai:test-planner",
                system_prompt="Task system prompt override",
                user_prompt_template="Task user prompt override: {{instruction}}",
            )
        )

        result = task_node.run("Aldera用长剑攻击goblin")

        self.assertEqual(
            [
                "actors.aldera.equipment.main_hand.attack_bonus = 7",
                "actors.goblin_1.hp.current = 7",
            ],
            result.states,
        )

    def test_task_node_keeps_evidence_excerpt_and_removes_duplicates(self) -> None:
        call_log: list[str] = []
        draft = TaskDraft(
            instruction="Aldera用火球术攻击goblin",
            normalized_instruction="Aldera用火球术攻击goblin",
            task="Resolve Fireball against goblin_1.",
            reads=["actors.aldera.spell_dc", "actors.goblin_1.abilities.dex.save"],
            judgments=["goblin_1 makes a Dexterity saving throw against Aldera's spell DC."],
            writes=["actors.goblin_1.hp.current"],
            missing_info=[],
            assumptions=[],
            evidence=[
                "火球术：20尺半径范围，敏捷豁免，失败全伤，成功半伤",
                "火球术：20尺半径范围，敏捷豁免，失败全伤，成功半伤",
                " 当前待结算目标是 actors.goblin_1 ",
            ],
            states=["actors.goblin_1.abilities.dex.save = 2"],
        )
        task_factory = RecordingAgentFactory(draft, "task", call_log)
        task_node = TaskNode(
            TaskNodeDependencies(
                agent_factory=task_factory,
                model="openai:test-planner",
                system_prompt="Task system prompt override",
                user_prompt_template="Task user prompt override: {{instruction}}",
            )
        )

        result = task_node.run("Aldera用火球术攻击goblin")

        self.assertEqual(
            [
                "火球术：20尺半径范围，敏捷豁免，失败全伤，成功半伤",
                "当前待结算目标是 actors.goblin_1",
            ],
            result.evidence,
        )
        self.assertFalse(hasattr(result, "read_values"))
        self.assertFalse(hasattr(result, "context_lines"))

    def test_task_node_adds_position_gap_for_area_effect_without_position_evidence(self) -> None:
        call_log: list[str] = []
        draft = TaskDraft(
            instruction="Aldera用火球术攻击goblin",
            normalized_instruction="Aldera用火球术攻击goblin",
            task="Resolve Fireball against goblin_1.",
            reads=["actors.aldera.spell_dc", "actors.aldera.spell_slots.level_3.current", "actors.goblin_1.abilities.dex.save"],
            judgments=["goblin_1 makes a Dexterity saving throw against Aldera's spell DC."],
            writes=["actors.aldera.spell_slots.level_3.current", "actors.goblin_1.hp.current"],
            missing_info=[],
            assumptions=[],
            evidence=["范围法术：20尺半径，敏捷豁免，失败全伤，成功半伤"],
            states=[
                "actors.aldera.spell_slots.level_3.current = 2",
                "actors.goblin_1.abilities.dex.save = 2",
            ],
        )
        task_factory = RecordingAgentFactory(draft, "task", call_log)
        task_node = TaskNode(
            TaskNodeDependencies(
                agent_factory=task_factory,
                model="openai:test-planner",
                system_prompt="Task system prompt override",
                user_prompt_template="Task user prompt override: {{instruction}}",
            )
        )

        result = task_node.run("Aldera用火球术攻击goblin")

        self.assertTrue(any("位置" in item or "覆盖范围" in item for item in result.missing_info))
        self.assertTrue(any("覆盖范围" in item or "受影响对象" in item for item in result.judgments))

    def test_task_node_keeps_area_effect_draft_complete_when_position_evidence_exists(self) -> None:
        call_log: list[str] = []
        draft = TaskDraft(
            instruction="Malik用闪电束攻击orc",
            normalized_instruction="Malik用闪电束攻击orc",
            task="Determine which creatures are in the lightning line and resolve the save result.",
            reads=[
                "actors.malik.spell_slots.level_3.current",
                "actors.malik.position.x",
                "actors.orc_1.position.x",
                "actors.orc_1.abilities.dex.save",
            ],
            judgments=[
                "先根据 Malik 与 orc_1 的位置确认闪电束直线是否覆盖 orc_1。",
                "orc_1 makes a Dexterity saving throw against Malik's spell DC.",
            ],
            writes=["actors.malik.spell_slots.level_3.current", "actors.orc_1.hp.current"],
            missing_info=[],
            assumptions=[],
            evidence=["闪电束：100尺直线，敏捷豁免，失败全伤，成功半伤"],
            states=[
                "actors.malik.position.x = 2",
                "actors.orc_1.position.x = 8",
                "actors.malik.spell_slots.level_3.current = 2",
            ],
        )
        task_factory = RecordingAgentFactory(draft, "task", call_log)
        task_node = TaskNode(
            TaskNodeDependencies(
                agent_factory=task_factory,
                model="openai:test-planner",
                system_prompt="Task system prompt override",
                user_prompt_template="Task user prompt override: {{instruction}}",
            )
        )

        result = task_node.run("Malik用闪电束攻击orc")

        self.assertFalse(any("位置" in item or "覆盖范围" in item for item in result.missing_info))


if __name__ == "__main__":
    unittest.main()
