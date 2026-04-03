from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "src")

from augury.planner import PlannerWorkflow, PlannerWorkflowDependencies
from augury.planner.nodes import DslNode, DslNodeDependencies, TaskNode, TaskNodeDependencies
from augury.planner.task_document import TaskDocumentSchema, TaskDraft
from augury.planner.tools import create_grep_tool, create_lint_tool, create_template_tool
from tests.config_helpers import write_project_config


class FakeAgent:
    def __init__(self, payload: object, call_log: list[str], marker: str) -> None:
        self.payload = payload
        self.call_log = call_log
        self.marker = marker
        self.invoke_configs: list[object] = []

    def invoke(self, state: dict[str, object], config: object | None = None) -> dict[str, object]:
        self.call_log.append(self.marker)
        self.call_log.append(state["messages"][0]["content"])  # type: ignore[index]
        self.invoke_configs.append(config)
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


class SequenceAgent:
    def __init__(self, responses: list[dict[str, object]], call_log: list[str], marker: str) -> None:
        self.responses = responses
        self.call_log = call_log
        self.marker = marker
        self.invocations = 0
        self.invoke_configs: list[object] = []

    def invoke(self, state: dict[str, object], config: object | None = None) -> dict[str, object]:
        self.call_log.append(self.marker)
        self.call_log.append(state["messages"][0]["content"])  # type: ignore[index]
        self.invoke_configs.append(config)
        index = min(self.invocations, len(self.responses) - 1)
        self.invocations += 1
        return self.responses[index]


class SequenceAgentFactory:
    def __init__(self, responses: list[dict[str, object]], marker: str, call_log: list[str]) -> None:
        self.responses = responses
        self.marker = marker
        self.call_log = call_log
        self.calls: list[dict[str, object]] = []
        self.agent: SequenceAgent | None = None

    def __call__(self, **kwargs: object) -> SequenceAgent:
        self.calls.append(kwargs)
        self.agent = SequenceAgent(self.responses, self.call_log, self.marker)
        return self.agent


class FakeLintTool:
    name = "lint"

    def __init__(self, results: list[dict[str, object]]) -> None:
        self.results = results
        self.calls: list[dict[str, object]] = []

    def invoke(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(payload)
        index = min(len(self.calls) - 1, len(self.results) - 1)
        return dict(self.results[index])


class FakeTemplateTool:
    name = "template"

    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def invoke(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(payload)
        return dict(self.result)


class ToolCallingAgent:
    def __init__(
        self,
        payload: dict[str, object],
        tools: list[object],
        call_log: list[str],
        marker: str,
    ) -> None:
        self.payload = payload
        self.call_log = call_log
        self.marker = marker
        self.tools = {getattr(tool, "name", f"tool_{index}"): tool for index, tool in enumerate(tools)}
        self.invoke_configs: list[object] = []

    def invoke(self, state: dict[str, object], config: object | None = None) -> dict[str, object]:
        self.call_log.append(self.marker)
        self.call_log.append(state["messages"][0]["content"])  # type: ignore[index]
        self.invoke_configs.append(config)
        template_result = self.tools["template"].invoke(
            {
                "task_family": "area spell or area effect",
                "resolution_mode": "save_damage",
                "resource_mode": "spell_slot",
                "targeting_mode": "center_on_target_position",
                "success_rule": "half",
            }
        )
        lint_result = self.tools["lint"].invoke({"task_document": self.payload})
        return {
            "structured_response": self.payload,
            "messages": [
                {"name": "template", "content": json.dumps(template_result, ensure_ascii=False)},
                {"name": "lint", "content": json.dumps(lint_result, ensure_ascii=False)},
            ],
        }


class ToolCallingAgentFactory:
    def __init__(self, payload: dict[str, object], marker: str, call_log: list[str]) -> None:
        self.payload = payload
        self.marker = marker
        self.call_log = call_log
        self.calls: list[dict[str, object]] = []
        self.agent: ToolCallingAgent | None = None

    def __call__(self, **kwargs: object) -> ToolCallingAgent:
        self.calls.append(kwargs)
        tools = kwargs.get("tools")
        self.agent = ToolCallingAgent(
            self.payload,
            list(tools) if isinstance(tools, list) else [],
            self.call_log,
            self.marker,
        )
        return self.agent


class PlannerWorkflowTests(unittest.TestCase):
    def test_dsl_node_prompt_files_define_engine_dsl_vocabulary_and_forbidden_terms(self) -> None:
        system_prompt = Path("config/prompts/planner_dsl_node_system.txt").read_text(encoding="utf-8")
        user_prompt = Path("config/prompts/planner_dsl_node_user.txt").read_text(encoding="utf-8")

        self.assertIn("select.target", system_prompt)
        self.assertIn("check.save", system_prompt)
        self.assertIn("resource.consume", system_prompt)
        self.assertIn("The internal `template` tool is available", system_prompt)
        self.assertIn("Prefer using `template` before relying on memory", system_prompt)
        self.assertIn("explicitly call `template` yourself", system_prompt)
        self.assertIn("Exact `template` enum literals", system_prompt)
        self.assertIn("Never send undocumented near-synonyms such as `area_spell`.", system_prompt)
        self.assertNotIn("prefetched `template_query_hint`", system_prompt)
        self.assertIn("The internal `lint` tool is available as the submission check", system_prompt)
        self.assertIn("Before you finalize the TaskDocument, use `lint` to check", system_prompt)
        self.assertIn("Your default goal is to return a TaskDocument that is `lint` valid", system_prompt)
        self.assertIn("If `lint` returns `invalid`, do not treat that invalid candidate as an acceptable final answer.", system_prompt)
        self.assertIn("continue revising and checking again until `lint` returns `valid`", system_prompt)
        self.assertIn("When `lint` returns structured issues with an `expected` template", system_prompt)
        self.assertIn("Do not invent project-external step types", system_prompt)
        self.assertIn("read`, `calculate`, `invoke`, `conditional`, or `write", system_prompt)
        self.assertIn("Build a valid TaskDocument in the current engine DSL.", user_prompt)
        self.assertIn("The final goal is to return a TaskDocument that is lint valid", user_prompt)
        self.assertIn('"task_draft": {{task_draft_json}}', user_prompt)
        self.assertNotIn("template_query_hint", user_prompt)
        self.assertNotIn("template_lookup", user_prompt)
        self.assertIn("call `template` with controlled enum fields", user_prompt)
        self.assertIn("use `unknown` instead of inventing a narrower signature", user_prompt)
        self.assertIn("Use exact template enum literals", user_prompt)
        self.assertIn("area spell or area effect", user_prompt)
        self.assertIn("Never send undocumented near-synonyms such as `area_spell`", user_prompt)
        self.assertIn("Before finalizing the TaskDocument, use `lint` to check", user_prompt)
        self.assertIn("If `lint` returns invalid, that candidate is not the ideal final answer.", user_prompt)
        self.assertIn("continue revising and checking again until `lint` returns valid", user_prompt)
        self.assertIn("If `lint` returns issues with an `expected` template", user_prompt)
        self.assertNotIn("repair_mode", user_prompt)
        self.assertNotIn("lint_budget", user_prompt)
        self.assertIn("Do not generate any step type outside select/check/damage/heal/resource/effect/state.", user_prompt)
        self.assertIn("translation_rules", user_prompt)

    def test_dsl_node_prompt_files_include_lowering_few_shots(self) -> None:
        user_prompt = Path("config/prompts/planner_dsl_node_user.txt").read_text(encoding="utf-8")

        self.assertIn("single-target attack", user_prompt)
        self.assertIn("area spell or area effect", user_prompt)
        self.assertIn("direct state update", user_prompt)
        self.assertIn('"type": "damage"', user_prompt)
        self.assertIn('"kind": "apply"', user_prompt)
        self.assertIn('"type": "resource"', user_prompt)
        self.assertIn('"kind": "consume"', user_prompt)

    def test_task_document_schema_rejects_project_external_step_types(self) -> None:
        with self.assertRaises(Exception):
            TaskDocumentSchema.model_validate(
                {
                    "task_id": "bad_dsl",
                    "version": 1,
                    "steps": [
                        {
                            "id": "step1",
                            "type": "read",
                            "kind": "ReadProperties",
                            "args": {"keys": ["actors.aldera.ac"]},
                        }
                    ],
                }
            )

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

    def test_dsl_node_uses_single_invoke_and_fallback_lint(self) -> None:
        call_log: list[str] = []
        draft = TaskDraft(
            instruction="Aldera用火球术攻击goblin",
            normalized_instruction="Aldera用火球术攻击goblin",
            task="Resolve Fireball against goblin_1.",
            reads=["actors.aldera.spell_dc", "actors.goblin_1.abilities.dex.save"],
            judgments=["goblin_1 makes a Dexterity saving throw against Aldera's spell DC."],
            writes=["actors.goblin_1.hp.current"],
            assumptions=[],
            missing_info=[],
            evidence=["火球术：敏捷豁免，失败全伤，成功半伤"],
            states=["actors.goblin_1.abilities.dex.save = 2"],
        )
        valid_document = {
            "task_id": "planner.fireball-save",
            "version": 1,
            "policy": {},
            "context": {},
            "steps": [
                {
                    "id": "dex_save",
                    "type": "check",
                    "kind": "save",
                    "args": {"dice": "1d20", "dc": 15},
                }
            ],
        }
        lint_tool = FakeLintTool(
            [
                {
                    "status": "valid",
                    "summary": "TaskDocument is valid.",
                    "issues": [],
                },
            ]
        )
        dsl_factory = SequenceAgentFactory(
            [{"structured_response": valid_document}],
            "dsl",
            call_log,
        )
        node = DslNode(
            DslNodeDependencies(
                lint_tool=lint_tool,
                agent_factory=dsl_factory,
                model="openai:test-planner",
                system_prompt="DSL system prompt override",
                user_prompt_template='{"task_draft":{{task_draft_json}}}',
            )
        )

        document, lint_result = node.run(draft)

        self.assertEqual("planner.fireball-save", document["task_id"])
        self.assertEqual("valid", lint_result["status"])
        self.assertEqual(1, len(lint_tool.calls))
        self.assertEqual(1, len(dsl_factory.calls))
        self.assertEqual(1, dsl_factory.agent.invocations)
        self.assertEqual({"recursion_limit": 13}, dsl_factory.agent.invoke_configs[0])
        self.assertIn('"task_draft":', call_log[1])
        self.assertEqual(1, lint_result["dsl_node_meta"]["lint_calls"])
        self.assertEqual(5, lint_result["dsl_node_meta"]["max_tool_calls"])
        self.assertTrue(lint_result["dsl_node_meta"]["used_fallback"])

    def test_dsl_node_uses_agent_emitted_lint_tool_result_without_fallback_invoke(self) -> None:
        call_log: list[str] = []
        draft = TaskDraft(
            instruction="Track Aldera AC",
            normalized_instruction="Track Aldera AC",
            task="Read Aldera AC and carry it into tracked state.",
            reads=["actors.aldera.ac"],
            judgments=["Use Aldera AC as the defensive threshold."],
            writes=["actors.aldera.ac"],
            assumptions=[],
            missing_info=[],
            evidence=[],
            states=[],
        )
        valid_document = {
            "task_id": "planner.track-aldera-ac",
            "version": 1,
            "policy": {},
            "context": {},
            "steps": [
                {
                    "id": "record_aldera_ac",
                    "type": "state",
                    "kind": "set",
                    "args": {"path": "actors.aldera.ac", "value": 18},
                }
            ],
        }
        lint_tool = FakeLintTool([{"status": "valid", "summary": "unused fallback", "issues": []}])
        dsl_factory = SequenceAgentFactory(
            [
                {
                    "structured_response": valid_document,
                    "messages": [
                        {
                            "name": "lint",
                            "content": json.dumps(
                                {"status": "valid", "summary": "TaskDocument is valid.", "issues": []},
                                ensure_ascii=False,
                            ),
                        }
                    ],
                }
            ],
            "dsl",
            call_log,
        )
        node = DslNode(
            DslNodeDependencies(
                lint_tool=lint_tool,
                agent_factory=dsl_factory,
                model="openai:test-planner",
                system_prompt="DSL system prompt override",
                user_prompt_template='{"task_draft":{{task_draft_json}}}',
            )
        )

        document, lint_result = node.run(draft)

        self.assertEqual("planner.track-aldera-ac", document["task_id"])
        self.assertEqual("valid", lint_result["status"])
        self.assertEqual([], lint_tool.calls)
        self.assertEqual(1, lint_result["dsl_node_meta"]["lint_calls"])
        self.assertFalse(lint_result["dsl_node_meta"]["used_fallback"])

    def test_dsl_node_records_fallback_lint_usage_when_agent_emits_no_lint_result(self) -> None:
        call_log: list[str] = []
        draft = TaskDraft(
            instruction="Track Aldera AC",
            normalized_instruction="Track Aldera AC",
            task="Read Aldera AC and carry it into tracked state.",
            reads=["actors.aldera.ac"],
            judgments=["Use Aldera AC as the defensive threshold."],
            writes=["actors.aldera.ac"],
            assumptions=[],
            missing_info=[],
            evidence=[],
            states=[],
        )
        valid_document = {
            "task_id": "planner.track-aldera-ac",
            "version": 1,
            "policy": {},
            "context": {},
            "steps": [
                {
                    "id": "record_aldera_ac",
                    "type": "state",
                    "kind": "set",
                    "args": {"path": "actors.aldera.ac", "value": 18},
                }
            ],
        }
        lint_tool = FakeLintTool([{"status": "valid", "summary": "fallback valid", "issues": []}])
        dsl_factory = SequenceAgentFactory(
            [{"structured_response": valid_document, "messages": []}],
            "dsl",
            call_log,
        )
        node = DslNode(
            DslNodeDependencies(
                lint_tool=lint_tool,
                agent_factory=dsl_factory,
                model="openai:test-planner",
                system_prompt="DSL system prompt override",
                user_prompt_template='{"task_draft":{{task_draft_json}}}',
            )
        )

        _, lint_result = node.run(draft)

        self.assertEqual(1, len(lint_tool.calls))
        self.assertEqual(1, lint_result["dsl_node_meta"]["lint_calls"])
        self.assertTrue(lint_result["dsl_node_meta"]["used_fallback"])
        self.assertEqual(5, lint_result["dsl_node_meta"]["max_tool_calls"])

    def test_dsl_node_prompt_can_reference_template_guidance_from_lint(self) -> None:
        user_prompt = Path("config/prompts/planner_dsl_node_user.txt").read_text(encoding="utf-8")

        self.assertIn("required fields", user_prompt)
        self.assertIn("allowed fields", user_prompt)
        self.assertIn("canonical example", user_prompt)
        self.assertIn("save_ability", user_prompt)
        self.assertIn("conditional_halving_on_save", user_prompt)
        self.assertIn("Use the returned issues and expected templates to improve the candidate", user_prompt)

    def test_template_tool_returns_area_spell_template_with_unknown_fallback(self) -> None:
        tool = create_template_tool()

        exact = tool.invoke(
            {
                "task_family": "area spell or area effect",
                "resolution_mode": "save_damage",
                "resource_mode": "spell_slot",
                "targeting_mode": "center_on_target_position",
                "success_rule": "half",
            }
        )
        fallback = tool.invoke(
            {
                "task_family": "area spell or area effect",
                "resolution_mode": "save_damage",
                "resource_mode": "unknown",
                "targeting_mode": "unknown",
                "success_rule": "unknown",
            }
        )

        self.assertEqual("ok", exact["status"])
        self.assertEqual("area-spell.save-damage-half.spell-slot", exact["template_id"])
        self.assertEqual(["select.area", "check.save", "damage.apply", "resource.consume"], exact["step_order"])
        self.assertEqual("ok", fallback["status"])
        self.assertTrue(fallback["fallback_used"])
        self.assertEqual("area-spell.save-damage-half.spell-slot", fallback["template_id"])
        self.assertIn("required_bindings", fallback)

    def test_template_tool_rejects_invalid_enum_input_with_structured_error(self) -> None:
        tool = create_template_tool()

        invalid = tool.invoke(
            {
                "task_family": "area_spell",
                "resolution_mode": "save_damage",
                "resource_mode": "spell_slot",
                "targeting_mode": "center_on_target_position",
                "success_rule": "half",
            }
        )

        self.assertEqual("error", invalid["status"])
        self.assertEqual("invalid_enum", invalid["error_type"])
        self.assertEqual("task_family", invalid["invalid_fields"][0]["field"])
        self.assertEqual("area_spell", invalid["invalid_fields"][0]["value"])
        self.assertIn("area spell or area effect", invalid["invalid_fields"][0]["allowed_values"])

    def test_template_tool_supports_area_spell_and_single_target_attack_documents_that_lint(self) -> None:
        template_tool = create_template_tool()
        lint_tool = create_lint_tool()

        area_template = template_tool.invoke(
            {
                "task_family": "area spell or area effect",
                "resolution_mode": "save_damage",
                "resource_mode": "spell_slot",
                "targeting_mode": "center_on_target_position",
                "success_rule": "half",
            }
        )
        attack_template = template_tool.invoke(
            {
                "task_family": "single-target attack",
                "resolution_mode": "attack_damage",
                "resource_mode": "none",
                "targeting_mode": "direct_target",
                "success_rule": "none",
            }
        )

        area_document = {
            "task_id": "planner.fireball-template-demo",
            "version": 1,
            "policy": {},
            "context": {},
            "steps": [
                {
                    "id": "select_area_targets",
                    "type": "select",
                    "kind": "area",
                    "args": {
                        "shape": "sphere",
                        "radius": 20,
                        "origin": {
                            "x": {"$ref": "state.actors.goblin_1.position.x"},
                            "y": {"$ref": "state.actors.goblin_1.position.y"},
                        },
                    },
                },
                {
                    "id": "saving_throw",
                    "type": "check",
                    "kind": "save",
                    "args": {
                        "dice": "1d20",
                        "ability": "dexterity",
                        "dc_path": "actors.aldera.spell_dc",
                        "targets": {"$ref": "result.select_area_targets.target_ids"},
                    },
                },
                {
                    "id": "apply_damage",
                    "type": "damage",
                    "kind": "apply",
                    "args": {
                        "targets": {"$ref": "result.select_area_targets.target_ids"},
                        "damage": [{"dice": "8d6", "damage_type": "fire"}],
                        "save_result": {"$ref": "result.saving_throw"},
                        "on_save": "half",
                    },
                },
                {
                    "id": "consume_resource",
                    "type": "resource",
                    "kind": "consume",
                    "args": {
                        "path": "actors.aldera.spell_slots.level_3.current",
                        "cost": 1,
                    },
                },
            ],
        }
        attack_document = {
            "task_id": "planner.attack-template-demo",
            "version": 1,
            "policy": {},
            "context": {},
            "steps": [
                {
                    "id": "attack_roll",
                    "type": "check",
                    "kind": "attack",
                    "args": {
                        "dice": "1d20",
                        "modifier": 5,
                        "target_id": "goblin_1",
                        "target_ac_path": "actors.goblin_1.ac.total",
                    },
                },
                {
                    "id": "apply_damage",
                    "type": "damage",
                    "kind": "apply",
                    "args": {
                        "targets": ["goblin_1"],
                        "damage": [{"dice": "1d8", "bonus": 3, "damage_type": "slashing"}],
                    },
                },
            ],
        }

        area_lint = lint_tool.invoke({"task_document": area_document})
        attack_lint = lint_tool.invoke({"task_document": attack_document})

        self.assertEqual("area-spell.save-damage-half.spell-slot", area_template["template_id"])
        self.assertEqual("single-target-attack.attack-damage", attack_template["template_id"])
        self.assertEqual("valid", area_lint["status"])
        self.assertEqual("valid", attack_lint["status"])

    def test_default_workflow_dsl_node_includes_template_and_lint_tools(self) -> None:
        workflow = PlannerWorkflow(state={"actors": {"aldera": {"ac": 18}}})

        self.assertEqual(["template", "lint"], [tool.name for tool in workflow.dsl_node.tools])

    def test_dsl_node_does_not_prefetch_template_when_agent_never_calls_it(self) -> None:
        call_log: list[str] = []
        draft = TaskDraft(
            instruction="Aldera用火球术攻击goblin_1所在位置",
            normalized_instruction="Aldera用火球术攻击goblin_1所在位置",
            task="Resolve Fireball centered on goblin_1 position.",
            reads=[
                "actors.aldera.spell_dc",
                "actors.aldera.spell_slots.level_3.current",
                "actors.goblin_1.position.x",
                "actors.goblin_1.position.y",
                "actors.goblin_1.abilities.dex.save",
            ],
            judgments=[
                "Determine which targets are inside the area.",
                "Each affected target makes a Dexterity save.",
                "Affected targets take fire damage.",
            ],
            writes=["actors.goblin_1.hp.current", "actors.aldera.spell_slots.level_3.current"],
            assumptions=[],
            missing_info=[],
            evidence=["火球术：敏捷豁免，失败全伤，成功半伤"],
            states=[],
        )
        valid_document = {
            "task_id": "planner.fireball-save",
            "version": 1,
            "policy": {},
            "context": {},
            "steps": [
                {
                    "id": "dex_save",
                    "type": "check",
                    "kind": "save",
                    "args": {"dice": "1d20", "dc": 15},
                }
            ],
        }
        template_tool = FakeTemplateTool(
            {
                "status": "ok",
                "template_id": "area-spell.save-damage-half.spell-slot",
                "step_order": ["select.area", "check.save", "damage.apply", "resource.consume"],
                "dsl_skeleton": {"steps": []},
                "required_bindings": ["dc_path"],
                "binding_rules": {"dc_path": "raw state path"},
                "common_mistakes": ["do not add state prefix to direct paths"],
            }
        )
        lint_tool = FakeLintTool([{"status": "valid", "summary": "fallback valid", "issues": []}])
        dsl_factory = SequenceAgentFactory(
            [{"structured_response": valid_document, "messages": []}],
            "dsl",
            call_log,
        )
        node = DslNode(
            DslNodeDependencies(
                template_tool=template_tool,
                lint_tool=lint_tool,
                agent_factory=dsl_factory,
                model="openai:test-planner",
                system_prompt="DSL system prompt override",
                user_prompt_template='{"task_draft":{{task_draft_json}}}',
            )
        )

        node.run(draft)

        self.assertEqual([], template_tool.calls)
        self.assertNotIn("template_query_hint", call_log[1])
        self.assertNotIn("template_lookup", call_log[1])

    def test_dsl_node_exposes_template_as_real_agent_tool_call(self) -> None:
        call_log: list[str] = []
        draft = TaskDraft(
            instruction="Aldera用火球术攻击goblin_1所在位置",
            normalized_instruction="Aldera用火球术攻击goblin_1所在位置",
            task="Resolve Fireball centered on goblin_1 position.",
            reads=[
                "actors.aldera.spell_dc",
                "actors.aldera.spell_slots.level_3.current",
                "actors.goblin_1.position.x",
                "actors.goblin_1.position.y",
                "actors.goblin_1.abilities.dex.save",
            ],
            judgments=[
                "Determine which targets are inside the area.",
                "Each affected target makes a Dexterity save.",
                "Affected targets take fire damage.",
            ],
            writes=["actors.goblin_1.hp.current", "actors.aldera.spell_slots.level_3.current"],
            assumptions=[],
            missing_info=[],
            evidence=["火球术：敏捷豁免，失败全伤，成功半伤"],
            states=[],
        )
        valid_document = {
            "task_id": "planner.fireball-save",
            "version": 1,
            "policy": {},
            "context": {},
            "steps": [
                {
                    "id": "dex_save",
                    "type": "check",
                    "kind": "save",
                    "args": {"dice": "1d20", "dc": 15},
                }
            ],
        }
        template_tool = FakeTemplateTool(
            {
                "status": "ok",
                "template_id": "area-spell.save-damage-half.spell-slot",
                "step_order": ["select.area", "check.save", "damage.apply", "resource.consume"],
                "dsl_skeleton": {"steps": []},
                "required_bindings": ["dc_path"],
                "binding_rules": {"dc_path": "raw state path"},
                "common_mistakes": ["do not add state prefix to direct paths"],
            }
        )
        lint_tool = FakeLintTool([{"status": "valid", "summary": "tool valid", "issues": []}])
        dsl_factory = ToolCallingAgentFactory(valid_document, "dsl", call_log)
        node = DslNode(
            DslNodeDependencies(
                template_tool=template_tool,
                lint_tool=lint_tool,
                agent_factory=dsl_factory,
                model="openai:test-planner",
                system_prompt="DSL system prompt override",
                user_prompt_template='{"task_draft":{{task_draft_json}}}',
            )
        )

        _, lint_result = node.run(draft)

        self.assertEqual(
            [
                {
                    "task_family": "area spell or area effect",
                    "resolution_mode": "save_damage",
                    "resource_mode": "spell_slot",
                    "targeting_mode": "center_on_target_position",
                    "success_rule": "half",
                }
            ],
            template_tool.calls,
        )
        self.assertEqual(1, len(lint_tool.calls))
        self.assertEqual(1, lint_result["dsl_node_meta"]["lint_calls"])
        self.assertFalse(lint_result["dsl_node_meta"]["used_fallback"])

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
