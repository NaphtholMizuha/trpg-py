from __future__ import annotations

from augury.planner.task_document import TaskBrief, TaskDocumentSchema, TaskDraft, validate_candidate_task_document


def __getattr__(name: str):
    if name in {"PlannerAgent", "PlannerDependencies", "create_planner"}:
        from augury.agent.runtime import PlannerAgent, PlannerDependencies, create_planner

        return {
            "PlannerAgent": PlannerAgent,
            "PlannerDependencies": PlannerDependencies,
            "create_planner": create_planner,
        }[name]
    if name in {"PlannerWorkflow", "PlannerWorkflowDependencies", "create_planner_workflow"}:
        from augury.planner.workflow import (
            PlannerWorkflow,
            PlannerWorkflowDependencies,
            create_planner_workflow,
        )

        return {
            "PlannerWorkflow": PlannerWorkflow,
            "PlannerWorkflowDependencies": PlannerWorkflowDependencies,
            "create_planner_workflow": create_planner_workflow,
        }[name]
    raise AttributeError(name)

__all__ = [
    "PlannerAgent",
    "PlannerDependencies",
    "PlannerWorkflow",
    "PlannerWorkflowDependencies",
    "TaskBrief",
    "TaskDocumentSchema",
    "TaskDraft",
    "create_planner",
    "create_planner_workflow",
    "validate_candidate_task_document",
]
