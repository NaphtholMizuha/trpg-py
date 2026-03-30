from __future__ import annotations

from typing import Any

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


TASK_DOCUMENT_OUTPUT_SCHEMA = TaskDocumentSchema.model_json_schema()


def validate_candidate_task_document(document: dict[str, Any] | None) -> None:
    TaskDocumentSchema.model_validate(document)
    validate_task_document(document or {})
