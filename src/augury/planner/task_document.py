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


class TaskDraft(BaseModel):
    instruction: str
    normalized_instruction: str
    task: str
    reads: list[str] = Field(
        default_factory=list,
        description="Exact state paths needed to resolve the task, including range and position prerequisites when relevant.",
    )
    judgments: list[str] = Field(
        default_factory=list,
        description="Resolution logic in execution order. Area effects should first determine coverage, then resolve each affected creature.",
    )
    writes: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(
        default_factory=list,
        description="Explicit gaps that block safe execution, such as missing slot-level, burst-center, or position evidence.",
    )
    assumptions: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(
        default_factory=list,
        description="Short rule or decisive state excerpts that help the next stage understand the task shape.",
    )
    states: list[str] = Field(
        default_factory=list,
        description="Short state-evidence lines supporting reads, writes, and range-coverage prerequisites.",
    )


class PlannerWorkflowState(BaseModel):
    instruction: str
    draft: TaskDraft | None = None
    task_document: dict[str, Any] | None = None
    lint_result: dict[str, Any] | None = None

    @property
    def brief(self) -> TaskDraft | None:
        return self.draft


class PlannerWorkflowResult(BaseModel):
    status: Literal["ready", "needs_human", "error"]
    instruction: str
    draft: TaskDraft | None = None
    task_document: dict[str, Any] | None = None
    lint_result: dict[str, Any] | None = None
    missing_info: list[str] = Field(default_factory=list)
    error: str | None = None

    @property
    def brief(self) -> TaskDraft | None:
        return self.draft


TASK_DOCUMENT_OUTPUT_SCHEMA = TaskDocumentSchema.model_json_schema()


def validate_candidate_task_document(document: dict[str, Any] | None) -> None:
    TaskDocumentSchema.model_validate(document)
    validate_task_document(document or {})


def normalize_instruction(value: str) -> str:
    collapsed = re.sub(r"\s+", " ", value or "")
    return collapsed.strip()


# Temporary compatibility alias while old imports are migrated.
TaskBrief = TaskDraft
