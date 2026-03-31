from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from augury.engine.core.executor import validate_task_document


class TaskStepSchema(BaseModel):
    id: str
    type: str
    kind: str
    args: dict[str, Any]
    tags: list[Any] = Field(default_factory=list)
    when: Any = None


class TaskDocumentSchema(BaseModel):
    task_id: str
    version: int
    policy: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    steps: list[TaskStepSchema]


class TaskBrief(BaseModel):
    instruction: str
    normalized_instruction: str
    summary: str
    action_shape: str = "task_brief"
    grep_expressions: list[str] = Field(default_factory=list)
    context_lines: list[str] = Field(default_factory=list)
    state_bindings: dict[str, Any] = Field(default_factory=dict)
    write_targets: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class PlannerWorkflowState(BaseModel):
    instruction: str
    brief: TaskBrief | None = None
    task_document: dict[str, Any] | None = None
    lint_result: dict[str, Any] | None = None


class PlannerWorkflowResult(BaseModel):
    status: Literal["ready", "needs_human", "error"]
    instruction: str
    brief: TaskBrief | None = None
    task_document: dict[str, Any] | None = None
    lint_result: dict[str, Any] | None = None
    missing_info: list[str] = Field(default_factory=list)
    error: str | None = None


TASK_DOCUMENT_OUTPUT_SCHEMA = TaskDocumentSchema.model_json_schema()


def validate_candidate_task_document(document: dict[str, Any] | None) -> None:
    TaskDocumentSchema.model_validate(document)
    validate_task_document(document or {})


def normalize_instruction(value: str) -> str:
    collapsed = re.sub(r"\s+", " ", value or "")
    return collapsed.strip()
