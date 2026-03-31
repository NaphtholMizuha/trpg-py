from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from augury.planner import PlannerWorkflow, PlannerWorkflowDependencies
from augury.planner.nodes import DslNode, DslNodeDependencies, IntentNode, IntentNodeDependencies
from augury.planner.task_document import TaskBrief
from augury.planner.tools import create_grep_tool, create_lint_tool, create_read_tool


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
        brief = TaskBrief(
            instruction="Review Aldera AC before the next turn",
            normalized_instruction="Review Aldera AC before the next turn",
            summary="Review Aldera AC before the next turn",
            action_shape="task_brief",
            context_lines=["actors.aldera.ac = 18"],
            state_bindings={"actors.aldera.ac": 18},
            write_targets=["actors.aldera.ac"],
        )
        document = {
            "task_id": "planner.review-aldera-ac",
            "version": 1,
            "policy": {},
            "context": {
                "instruction": brief.instruction,
                "task_brief": brief.model_dump(),
            },
            "steps": [
                {
                    "id": "apply_brief",
                    "type": "state",
                    "kind": "set",
                    "args": {
                        "path": "actors.aldera.ac",
                        "value": {
                            "instruction": brief.instruction,
                            "summary": brief.summary,
                            "action_shape": brief.action_shape,
                        },
                    },
                }
            ],
        }
        intent_factory = RecordingAgentFactory(brief, "intent", call_log)
        dsl_factory = RecordingAgentFactory(document, "dsl", call_log)

        intent_node = IntentNode(
            IntentNodeDependencies(
                grep_tool=create_grep_tool(state=state),
                read_tool=create_read_tool(state=state),
                agent_factory=intent_factory,
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
                intent_node=intent_node,
                dsl_node=dsl_node,
            ),
        )

        result = workflow.invoke("Review Aldera AC before the next turn")

        self.assertEqual("ready", result.status)
        self.assertEqual("intent", call_log[0])
        self.assertEqual("dsl", call_log[2])
        self.assertEqual("valid", result.lint_result["status"])
        self.assertEqual("planner.review-aldera-ac", result.task_document["task_id"])
        self.assertEqual(1, len(intent_factory.calls))
        self.assertEqual(1, len(dsl_factory.calls))
        self.assertEqual("planner_intent_node", intent_factory.calls[0]["name"])
        self.assertEqual("planner_dsl_node", dsl_factory.calls[0]["name"])
        self.assertEqual(2, len(intent_factory.calls[0]["tools"]))
        self.assertEqual(1, len(dsl_factory.calls[0]["tools"]))


if __name__ == "__main__":
    unittest.main()
