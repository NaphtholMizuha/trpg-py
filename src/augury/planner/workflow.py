from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from augury.planner.nodes import DslNode, DslNodeDependencies, TaskNode, TaskNodeDependencies
from augury.planner.task_document import PlannerWorkflowResult, TaskDraft
from augury.planner.tools import create_grep_tool, create_lint_tool, create_template_tool


class PlannerGraphState(TypedDict, total=False):
    instruction: str
    draft: TaskDraft
    task_document: dict[str, Any]
    lint_result: dict[str, Any] | None
    missing_info: list[str]


@dataclass(slots=True)
class PlannerWorkflowDependencies:
    task_node: TaskNode | None = None
    intent_node: TaskNode | None = None
    dsl_node: DslNode | None = None

    def __post_init__(self) -> None:
        if self.task_node is None and self.intent_node is not None:
            self.task_node = self.intent_node


class PlannerWorkflow:
    def __init__(
        self,
        *,
        state: dict | None = None,
        dependencies: PlannerWorkflowDependencies | None = None,
    ) -> None:
        self.state = state or {}
        self.dependencies = dependencies or PlannerWorkflowDependencies()
        self.task_node = self.dependencies.task_node or TaskNode(
            TaskNodeDependencies(
                grep_tool=create_grep_tool(state=self.state),
            )
        )
        self.dsl_node = self.dependencies.dsl_node or DslNode(
            DslNodeDependencies(
                template_tool=create_template_tool(),
                lint_tool=create_lint_tool(),
            )
        )
        self.graph = self._build_graph()

    def invoke(self, instruction: str) -> PlannerWorkflowResult:
        final_state = self.graph.invoke({"instruction": instruction})
        draft = final_state.get("draft")
        task_document = final_state.get("task_document")
        lint_result = final_state.get("lint_result")
        missing_info = list(final_state.get("missing_info", []))
        if missing_info:
            return PlannerWorkflowResult(
                status="needs_human",
                instruction=instruction,
                draft=draft,
                task_document=task_document,
                lint_result=lint_result,
                missing_info=missing_info,
            )
        if lint_result is not None and lint_result.get("status") != "valid":
            return PlannerWorkflowResult(
                status="needs_human",
                instruction=instruction,
                draft=draft,
                task_document=task_document,
                lint_result=lint_result,
                missing_info=["generated task document did not pass lint"],
            )
        return PlannerWorkflowResult(
            status="ready",
            instruction=instruction,
            draft=draft,
            task_document=task_document,
            lint_result=lint_result,
        )

    def _build_graph(self):
        graph = StateGraph(PlannerGraphState)
        graph.add_node("task_node", self._run_task_node)
        graph.add_node("dsl_node", self._run_dsl_node)
        graph.add_edge(START, "task_node")
        graph.add_conditional_edges(
            "task_node",
            self._route_after_task,
            {"dsl": "dsl_node", "end": END},
        )
        graph.add_edge("dsl_node", END)
        return graph.compile()

    def _run_task_node(self, state: PlannerGraphState) -> PlannerGraphState:
        draft = self.task_node.run(state["instruction"])
        return {
            "draft": draft,
            "missing_info": list(draft.missing_info),
        }

    def _run_dsl_node(self, state: PlannerGraphState) -> PlannerGraphState:
        draft = state["draft"]
        task_document, lint_result = self.dsl_node.run(draft)
        return {
            "task_document": task_document,
            "lint_result": lint_result,
        }

    @staticmethod
    def _route_after_task(state: PlannerGraphState) -> str:
        if state.get("missing_info"):
            return "end"
        return "dsl"


def create_planner_workflow(
    *,
    state: dict | None = None,
    dependencies: PlannerWorkflowDependencies | None = None,
) -> PlannerWorkflow:
    return PlannerWorkflow(state=state, dependencies=dependencies)
