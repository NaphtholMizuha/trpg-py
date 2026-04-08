from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorInfo(BaseModel):
    type: str
    message: str


class Citation(BaseModel):
    source: str
    locator: str | None = None
    detail: str | None = None


class EvidenceItem(BaseModel):
    kind: Literal["rule", "state"]
    summary: str
    source: str | None = None
    locator: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class AskOption(BaseModel):
    id: str
    label: str
    description: str | None = None


class AskRequest(BaseModel):
    question_id: str
    prompt: str
    options: list[AskOption] = Field(default_factory=list)
    default_option_id: str | None = None
    allow_custom_input: bool = False
    custom_input_label: str | None = None
    custom_input_placeholder: str | None = None
    reason: str | None = None


class AskResponse(BaseModel):
    question_id: str
    selected_option_id: str | None = None
    custom_input: str | None = None


class PendingInterrupt(BaseModel):
    tool_name: str
    kind: Literal["ask"] = "ask"
    request: AskRequest


class ContextBundle(BaseModel):
    status: Literal["ready", "needs_human", "blocked", "error"] = "ready"
    instruction: str
    normalized_instruction: str
    action: str | None = None
    resolved_entities: dict[str, str] = Field(default_factory=dict)
    derived_context: dict[str, Any] = Field(default_factory=dict)
    rule_evidence: list[EvidenceItem] = Field(default_factory=list)
    state_evidence: list[EvidenceItem] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    ask_requests: list[AskRequest] = Field(default_factory=list)
    ask_responses: list[AskResponse] = Field(default_factory=list)
    pending_interrupt: PendingInterrupt | None = None
    notes: list[str] = Field(default_factory=list)
    error: ErrorInfo | None = None


class ResolutionBundle(BaseModel):
    status: Literal["ready", "blocked", "error"] = "ready"
    task_document: dict[str, Any] | None = None
    lint_result: dict[str, Any] | None = None
    execution_report: dict[str, Any] | None = None
    state_changes: list[dict[str, Any]] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    error: ErrorInfo | None = None


class PlannerRequest(BaseModel):
    instruction: str
    state: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    ask_responses: list[AskResponse] = Field(default_factory=list)
    task_document: dict[str, Any] | None = None
    config_path: str | None = None


class PlannerResult(BaseModel):
    status: Literal["ready", "needs_human", "blocked", "error"]
    instruction: str
    loaded_skills: list[str] = Field(default_factory=list)
    context_bundle: ContextBundle | None = None
    resolution_bundle: ResolutionBundle | None = None
    task_document: dict[str, Any] | None = None
    lint_result: dict[str, Any] | None = None
    execution_report: dict[str, Any] | None = None
    state_changes: list[dict[str, Any]] = Field(default_factory=list)
    ask_requests: list[AskRequest] = Field(default_factory=list)
    ask_responses: list[AskResponse] = Field(default_factory=list)
    pending_interrupt: PendingInterrupt | None = None
    missing_info: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    error: ErrorInfo | None = None
