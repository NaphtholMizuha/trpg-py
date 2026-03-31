from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from augury.planner.nodes import DslNode, DslNodeDependencies, IntentNode, IntentNodeDependencies
from augury.planner.task_document import PlannerWorkflowResult, TaskBrief
from augury.planner.tools import create_grep_tool, create_lint_tool, create_read_tool


class PlannerGraphState(TypedDict, total=False):
    instruction: str
    brief: TaskBrief
    task_document: dict[str, Any]
    lint_result: dict[str, Any] | None
    missing_info: list[str]


@dataclass(slots=True)
class PlannerWorkflowDependencies:
    intent_node: IntentNode | None = None
    dsl_node: DslNode | None = None


class PlannerWorkflow:
    def __init__(
        self,
        *,
        state: dict | None = None,
        dependencies: PlannerWorkflowDependencies | None = None,
    ) -> None:
        self.state = state or {}
        self.dependencies = dependencies or PlannerWorkflowDependencies()
        self.intent_node = self.dependencies.intent_node or IntentNode(
            IntentNodeDependencies(
                grep_tool=create_grep_tool(state=self.state),
                read_tool=create_read_tool(state=self.state),
            )
        )
        self.dsl_node = self.dependencies.dsl_node or DslNode(
            DslNodeDependencies(
                lint_tool=create_lint_tool(),
            )
        )
        self.graph = self._build_graph()

    def invoke(self, instruction: str) -> PlannerWorkflowResult:
        final_state = self.graph.invoke({"instruction": instruction})
        brief = final_state.get("brief")
        task_document = final_state.get("task_document")
        lint_result = final_state.get("lint_result")
        missing_info = list(final_state.get("missing_info", []))
        if missing_info:
            return PlannerWorkflowResult(
                status="needs_human",
                instruction=instruction,
                brief=brief,
                task_document=task_document,
                lint_result=lint_result,
                missing_info=missing_info,
            )
        if lint_result is not None and lint_result.get("status") != "valid":
            return PlannerWorkflowResult(
                status="needs_human",
                instruction=instruction,
                brief=brief,
                task_document=task_document,
                lint_result=lint_result,
                missing_info=["generated task document did not pass lint"],
            )
        return PlannerWorkflowResult(
            status="ready",
            instruction=instruction,
            brief=brief,
            task_document=task_document,
            lint_result=lint_result,
        )

    def _build_graph(self):
        graph = StateGraph(PlannerGraphState)
        graph.add_node("intent_node", self._run_intent_node)
        graph.add_node("dsl_node", self._run_dsl_node)
        graph.add_edge(START, "intent_node")
        graph.add_conditional_edges(
            "intent_node",
            self._route_after_intent,
            {"dsl": "dsl_node", "end": END},
        )
        graph.add_edge("dsl_node", END)
        return graph.compile()

    def _run_intent_node(self, state: PlannerGraphState) -> PlannerGraphState:
        brief = self.intent_node.run(state["instruction"])
        return {
            "brief": brief,
            "missing_info": list(brief.missing_info),
        }

    def _run_dsl_node(self, state: PlannerGraphState) -> PlannerGraphState:
        brief = state["brief"]
        task_document, lint_result = self.dsl_node.run(brief)
        return {
            "task_document": task_document,
            "lint_result": lint_result,
        }

    @staticmethod
    def _route_after_intent(state: PlannerGraphState) -> str:
        if state.get("missing_info"):
            return "end"
        return "dsl"


def create_planner_workflow(
    *,
    state: dict | None = None,
    dependencies: PlannerWorkflowDependencies | None = None,
) -> PlannerWorkflow:
    return PlannerWorkflow(state=state, dependencies=dependencies)
