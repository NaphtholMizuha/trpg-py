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
            context_lines=["actors.aldera.ac = 18"],
            read_values={"actors.aldera.ac": 18},
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
            context_lines=["actors.aldera.ac = 18"],
            read_values={"actors.aldera.ac": 18},
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
                planner_task_node_user_prompt_template="Task user prompt from file: {{instruction}}",
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

        self.assertEqual("Task system prompt from file", task_factory.calls[0]["system_prompt"])
        self.assertEqual("DSL system prompt from file", dsl_factory.calls[0]["system_prompt"])
        self.assertEqual("Task user prompt from file: Track Aldera AC", call_log[1])
        self.assertIn('"instruction": "Track Aldera AC"', call_log[3])
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
            context_lines=["actors.malik.hp.current = 22"],
            read_values={"actors.malik.hp.current": 22},
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
                planner_task_node_user_prompt_template="Task user prompt from file: {{instruction}}",
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
                    user_prompt_template="Task user prompt override: {{instruction}}",
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
        self.assertEqual("Task user prompt override: Track Malik HP", call_log[1])
        self.assertTrue(call_log[3].startswith("DSL user prompt override: "))
        self.assertIn('"instruction": "Track Malik HP"', call_log[3])
        self.assertEqual("planner.track-malik-hp", dsl_result["task_id"])
        self.assertEqual("valid", lint_result["status"])


if __name__ == "__main__":
    unittest.main()
