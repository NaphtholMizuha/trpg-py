from __future__ import annotations

import importlib
import json
import re
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, TypedDict
from uuid import uuid4

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.agents.middleware.tool_call_limit import ToolCallLimitExceededError, ToolCallLimitMiddleware
from langchain.agents.structured_output import StructuredOutputValidationError, ToolStrategy
from langchain.chat_models import init_chat_model
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError, model_validator

from trpg_py.agent.planner_logging import (
    build_planner_log_path,
    resolve_project_root,
    serialize_for_log,
    summarize_ai_message,
)
from trpg_py.agent.planner_runtime_guards import (
    PlannerGuardEvent,
    activate_planner_runtime_guard,
    build_guard_missing_info,
)
from trpg_py.agent.task_document import TASK_DOCUMENT_OUTPUT_SCHEMA, validate_candidate_task_document
from trpg_py.agent.tools import (
    FetchKeysTool,
    ListTool,
    LintTool,
    ReadTool,
    ReadsTool,
    SearchTool,
    create_list_tool,
    create_fetch_keys_tool,
    create_lint_tool,
    create_read_tool,
    create_reads_tool,
    create_search_tool,
)
from trpg_py.config import ProjectConfig, load_project_config, resolve_path_from_config
from trpg_py.errors import DiceError, ValidationError


class PlannerQuestion(BaseModel):
    question: str = Field(min_length=1)
    missing_info: str | None = None
    why: str | None = None
    options: list[str] = Field(default_factory=list)


class PlannerError(BaseModel):
    type: str
    message: str


class PlannerResumeToken(BaseModel):
    thread_id: str = Field(min_length=1)


class EvidenceFact(BaseModel):
    name: str = Field(min_length=1)
    value_summary: str = Field(min_length=1)
    source_paths: list[str] = Field(default_factory=list)
    source_kind: Literal["instruction", "state", "rule", "derived"] = "state"
    note: str | None = None


class EvidenceBundle(BaseModel):
    summary: str = Field(min_length=1)
    facts: list[EvidenceFact] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    ready_for_dsl: bool = False


class EvidenceAgentResult(BaseModel):
    status: Literal["ready", "needs_human", "blocked"]
    evidence_bundle: EvidenceBundle | None = None
    questions: list[PlannerQuestion] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    error: PlannerError | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_state(self) -> "EvidenceAgentResult":
        if self.status == "ready" and self.evidence_bundle is None:
            raise ValueError("ready evidence result requires evidence_bundle")
        if self.status == "needs_human" and not self.questions:
            raise ValueError("needs_human evidence result requires at least one question")
        if self.status == "blocked" and self.error is None:
            raise ValueError("blocked evidence result requires error")
        return self


class PendingPlannerState(BaseModel):
    stage: Literal["evidence_agent", "dsl_agent"]
    evidence_bundle: EvidenceBundle | None = None
    validation_feedback: str | None = None
    resume_with_command: bool = False


class PlannerStagePause(BaseModel):
    stage: Literal["evidence_agent", "dsl_agent"]
    questions: list[PlannerQuestion] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    reason: str | None = None
    error: PlannerError | None = None
    evidence_bundle: EvidenceBundle | None = None
    validation_feedback: str | None = None
    resume_with_command: bool = False
    debug: PlannerDebugInfo | None = None


class PlannerDebugAttempt(BaseModel):
    round: int = Field(ge=1)
    input_mode: Literal["prompt", "resume"]
    phase: Literal["planning", "forced_finalize", "evidence_agent", "dsl_agent"] = "planning"
    response_snapshot: Any = None
    repair_feedback: str | None = None
    validation_error: str | None = None


class PlannerDebugInfo(BaseModel):
    attempts: list[PlannerDebugAttempt] = Field(default_factory=list)
    failure_stage: Literal[
        "human_review",
        "agent_error",
        "schema_or_semantic_validation",
        "runtime_guard",
        "forced_finalize",
    ] | None = None
    failure_message: str | None = None
    guard_events: list[PlannerGuardEvent] = Field(default_factory=list)


class PlannerRequest(BaseModel):
    instruction: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory=dict)
    thread_id: str | None = None
    resume: Any = None
    debug: bool = False

    @model_validator(mode="after")
    def validate_resume_state(self) -> "PlannerRequest":
        if self.resume is not None and not self.thread_id:
            raise ValueError("resume requires thread_id")
        return self


class PlannerResult(BaseModel):
    status: Literal["ready", "needs_human", "blocked"]
    task_document: dict[str, Any] | None = None
    questions: list[PlannerQuestion] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    error: PlannerError | None = None
    resume: PlannerResumeToken | None = None
    reason: str | None = None
    debug: PlannerDebugInfo | None = None

    @model_validator(mode="after")
    def validate_state(self) -> "PlannerResult":
        if self.status == "ready" and self.task_document is None:
            raise ValueError("ready result requires task_document")
        if self.status == "needs_human" and not self.questions:
            raise ValueError("needs_human result requires at least one question")
        if self.status == "blocked" and self.error is None:
            raise ValueError("blocked result requires error")
        return self


PLANNER_RESULT_SCHEMA = PlannerResult.model_json_schema()


class PlannerFactoryConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: Any
    base_url: str | None = None
    api_key: str | None = None
    timeout: float = Field(gt=0)
    max_retries: int = Field(ge=0)
    interrupt_on: dict[str, Any] = Field(default_factory=dict)
    max_planning_rounds: int = Field(ge=1)
    tool_budget: int = Field(ge=1)
    system_prompt_template: str = Field(min_length=1)
    user_prompt_template: str = Field(min_length=1)


class PlannerGraphState(TypedDict, total=False):
    request: dict[str, Any]
    thread_id: str
    attempts: list[PlannerDebugAttempt]
    evidence_bundle: EvidenceBundle
    validation_feedback: str | None
    final_result: PlannerResult
    pause: dict[str, Any]
    human_resume: Any


class Planner:
    def __init__(
        self,
        *,
        evidence_agent: Any,
        dsl_agent: Any,
        config: PlannerFactoryConfig,
        project_root: Path,
        search_tool: SearchTool,
        list_tool: ListTool | FetchKeysTool,
        read_tool: ReadTool | ReadsTool,
        lint_tool: LintTool,
        forced_finalize_agent_factory: Callable[[], Any] | None = None,
        graph_checkpointer: Any | None = None,
    ) -> None:
        self.evidence_agent = evidence_agent
        self.dsl_agent = dsl_agent
        self.config = config
        self.project_root = project_root
        self.search_tool = search_tool
        self.list_tool = list_tool
        self.read_tool = read_tool
        self.fetch_keys_tool = list_tool
        self.reads_tool = read_tool
        self.lint_tool = lint_tool
        self._forced_finalize_agent_factory = forced_finalize_agent_factory
        self._forced_finalize_agent: Any | None = None
        self._pending_states: dict[str, PendingPlannerState] = {}
        self._graph = self._build_planner_graph(graph_checkpointer)
        self.last_run_id: str | None = None
        self.last_run_log_path: str | None = None

    def plan(self, request: PlannerRequest | dict[str, Any]) -> PlannerResult:
        planner_request = PlannerRequest.model_validate(request)
        run_id = uuid4().hex[:12]
        thread_id = planner_request.thread_id or self._resolve_thread_id(planner_request)
        log_path = build_planner_log_path(self.project_root, run_id)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        sink_id = logger.add(log_path, serialize=True, level="INFO", diagnose=False, backtrace=False)
        self.last_run_id = run_id
        self.last_run_log_path = str(log_path)

        result: PlannerResult | None = None
        try:
            with logger.contextualize(planner_run_id=run_id, planner_thread_id=thread_id or "-", planner_round="-", planner_input_mode="-"):
                logger.bind(
                    planner_event="run_start",
                    planner_instruction=serialize_for_log(planner_request.instruction),
                    planner_context=serialize_for_log(planner_request.context),
                    planner_policy=serialize_for_log(planner_request.policy),
                    planner_debug=planner_request.debug,
                    planner_model=serialize_for_log(self.config.model),
                    planner_tool_budget=self.config.tool_budget,
                    planner_max_rounds=self.config.max_planning_rounds,
                    planner_log_path=str(log_path),
                ).info("planner run started")
                graph_input: Any
                if planner_request.resume is not None:
                    graph_input = Command(resume=planner_request.resume)
                else:
                    graph_input = {
                        "request": planner_request.model_dump(exclude_none=True),
                        "thread_id": thread_id,
                        "attempts": [],
                        "validation_feedback": None,
                        "human_resume": None,
                    }
                raw_graph_result = self._graph.invoke(graph_input, config=self._build_run_config(thread_id))
                result = self._coerce_graph_result(
                    raw_graph_result,
                    request=planner_request,
                    thread_id=thread_id,
                )

                logger.bind(
                    planner_event="run_end",
                    planner_status=result.status,
                    planner_reason=result.reason,
                    planner_error_type=result.error.type if result.error else None,
                    planner_error_message=result.error.message if result.error else None,
                ).info("planner run finished")
                return result
        except Exception as exc:
            logger.bind(
                planner_event="unexpected_error",
                planner_error_type=exc.__class__.__name__,
                planner_error_detail=self._build_exception_log_payload(exc),
                planner_traceback=traceback.format_exc(),
            ).error("planner run crashed unexpectedly")
            raise
        finally:
            logger.remove(sink_id)

    def _coerce_planner_result(self, raw_response: Any) -> PlannerResult:
        payload = raw_response
        if isinstance(raw_response, dict) and "structured_response" in raw_response:
            payload = raw_response["structured_response"]
        if isinstance(payload, BaseModel):
            payload = payload.model_dump(exclude_none=True)
        return PlannerResult.model_validate(payload)

    def _coerce_evidence_result(self, raw_response: Any) -> EvidenceAgentResult:
        payload = raw_response
        if isinstance(raw_response, dict) and "structured_response" in raw_response:
            payload = raw_response["structured_response"]
        if isinstance(payload, BaseModel):
            payload = payload.model_dump(exclude_none=True)
        return EvidenceAgentResult.model_validate(payload)

    def _coerce_graph_result(
        self,
        raw_graph_result: Any,
        *,
        request: PlannerRequest,
        thread_id: str | None,
    ) -> PlannerResult:
        if isinstance(raw_graph_result, dict) and "__interrupt__" in raw_graph_result:
            return self._coerce_graph_interrupt_result(
                raw_graph_result["__interrupt__"],
                request=request,
                thread_id=thread_id,
            )
        if isinstance(raw_graph_result, dict) and "final_result" in raw_graph_result:
            return self._coerce_planner_result(raw_graph_result["final_result"])
        return self._coerce_planner_result(raw_graph_result)

    def _coerce_graph_interrupt_result(
        self,
        interrupts: Any,
        *,
        request: PlannerRequest,
        thread_id: str | None,
    ) -> PlannerResult:
        payload = None
        interrupt_items = interrupts if isinstance(interrupts, list | tuple) else [interrupts]
        for interrupt_item in interrupt_items:
            value = getattr(interrupt_item, "value", interrupt_item)
            if isinstance(value, dict) and isinstance(value.get("planner_pause"), dict):
                payload = value["planner_pause"]
                break
        if payload is None:
            fallback = self._coerce_interrupt_result({"__interrupt__": interrupts}, thread_id=thread_id)
            if fallback is None:
                raise ValueError("planner graph returned an interrupt payload that could not be interpreted")
            fallback.debug = self._build_debug_info(request, attempts=[], failure_stage="human_review")
            return fallback

        pause_result = PlannerResult(
            status="needs_human",
            questions=[PlannerQuestion.model_validate(item) for item in payload.get("questions", [])],
            missing_info=[str(item) for item in payload.get("missing_info", [])],
            assumptions=[str(item) for item in payload.get("assumptions", [])],
            reason=payload.get("reason") or "needs_human",
            error=PlannerError.model_validate(payload["error"]) if payload.get("error") else None,
            resume=PlannerResumeToken(thread_id=thread_id) if thread_id else None,
            debug=PlannerDebugInfo.model_validate(payload.get("debug", {})) if payload.get("debug") else None,
        )
        return pause_result

    def _build_planner_graph(self, checkpointer: Any | None) -> Any:
        graph = StateGraph(PlannerGraphState)
        graph.add_node("evidence_agent", self._graph_run_evidence_agent)
        graph.add_node("dsl_agent", self._graph_run_dsl_agent)
        graph.add_node("human_review", self._graph_human_review)
        graph.add_edge(START, "evidence_agent")
        graph.add_conditional_edges(
            "evidence_agent",
            self._route_after_evidence_agent,
            {
                "dsl_agent": "dsl_agent",
                "human_review": "human_review",
                "end": END,
            },
        )
        graph.add_conditional_edges(
            "dsl_agent",
            self._route_after_dsl_agent,
            {
                "human_review": "human_review",
                "end": END,
            },
        )
        graph.add_conditional_edges(
            "human_review",
            self._route_after_human_review,
            {
                "evidence_agent": "evidence_agent",
                "dsl_agent": "dsl_agent",
            },
        )
        return graph.compile(checkpointer=checkpointer)

    def _graph_run_evidence_agent(self, state: PlannerGraphState) -> dict[str, Any]:
        request = PlannerRequest.model_validate(state["request"])
        thread_id = state.get("thread_id")
        attempts = list(state.get("attempts") or [])
        pause = PlannerStagePause.model_validate(state["pause"]) if state.get("pause") else None
        evidence_outcome = self._run_evidence_stage(
            request,
            thread_id=thread_id,
            attempts=attempts,
            resume_payload=state.get("human_resume"),
            resume_with_command=bool(pause and pause.stage == "evidence_agent" and pause.resume_with_command),
        )
        if isinstance(evidence_outcome, PlannerStagePause):
            return {
                "attempts": attempts,
                "pause": evidence_outcome.model_dump(exclude_none=True),
                "human_resume": None,
            }
        if isinstance(evidence_outcome, PlannerResult):
            if evidence_outcome.status == "needs_human":
                return {
                    "attempts": attempts,
                    "pause": PlannerStagePause(
                        stage="evidence_agent",
                        questions=evidence_outcome.questions,
                        missing_info=evidence_outcome.missing_info,
                        assumptions=evidence_outcome.assumptions,
                        reason=evidence_outcome.reason,
                        error=evidence_outcome.error,
                        debug=evidence_outcome.debug,
                    ).model_dump(exclude_none=True),
                    "human_resume": None,
                }
            return {
                "attempts": attempts,
                "final_result": evidence_outcome,
                "human_resume": None,
            }
        return {
            "attempts": attempts,
            "evidence_bundle": evidence_outcome,
            "pause": None,
            "human_resume": None,
            "validation_feedback": None,
        }

    def _graph_run_dsl_agent(self, state: PlannerGraphState) -> dict[str, Any]:
        request = PlannerRequest.model_validate(state["request"])
        thread_id = state.get("thread_id")
        attempts = list(state.get("attempts") or [])
        pause = PlannerStagePause.model_validate(state["pause"]) if state.get("pause") else None
        dsl_outcome = self._run_dsl_stage(
            request,
            evidence_bundle=state.get("evidence_bundle"),
            thread_id=thread_id,
            attempts=attempts,
            resume_payload=state.get("human_resume"),
            validation_feedback=(pause.validation_feedback if pause and pause.stage == "dsl_agent" else state.get("validation_feedback")),
            resume_with_command=bool(pause and pause.stage == "dsl_agent" and pause.resume_with_command),
        )
        if isinstance(dsl_outcome, PlannerStagePause):
            return {
                "attempts": attempts,
                "pause": dsl_outcome.model_dump(exclude_none=True),
                "human_resume": None,
                "validation_feedback": dsl_outcome.validation_feedback,
            }
        if dsl_outcome.status == "needs_human":
            return {
                "attempts": attempts,
                "pause": PlannerStagePause(
                    stage="dsl_agent",
                    questions=dsl_outcome.questions,
                    missing_info=dsl_outcome.missing_info,
                    assumptions=dsl_outcome.assumptions,
                    reason=dsl_outcome.reason,
                    error=dsl_outcome.error,
                    evidence_bundle=state.get("evidence_bundle"),
                    validation_feedback=(pause.validation_feedback if pause and pause.stage == "dsl_agent" else state.get("validation_feedback")),
                    debug=dsl_outcome.debug,
                ).model_dump(exclude_none=True),
                "human_resume": None,
            }
        return {
            "attempts": attempts,
            "final_result": dsl_outcome,
            "pause": None,
            "human_resume": None,
        }

    def _graph_human_review(self, state: PlannerGraphState) -> dict[str, Any]:
        pause = PlannerStagePause.model_validate(state["pause"])
        human_resume = interrupt(
            {
                "planner_pause": {
                    "stage": pause.stage,
                    "questions": [item.model_dump(exclude_none=True) for item in pause.questions],
                    "missing_info": list(pause.missing_info),
                    "assumptions": list(pause.assumptions),
                    "reason": pause.reason,
                    "error": pause.error.model_dump(exclude_none=True) if pause.error else None,
                    "debug": pause.debug.model_dump(exclude_none=True) if pause.debug else None,
                }
            }
        )
        return {
            "human_resume": human_resume,
        }

    def _route_after_evidence_agent(self, state: PlannerGraphState) -> str:
        if state.get("final_result") is not None:
            return "end"
        if state.get("pause") is not None:
            return "human_review"
        return "dsl_agent"

    def _route_after_dsl_agent(self, state: PlannerGraphState) -> str:
        if state.get("pause") is not None:
            return "human_review"
        return "end"

    def _route_after_human_review(self, state: PlannerGraphState) -> str:
        pause = PlannerStagePause.model_validate(state["pause"]) if state.get("pause") else None
        if pause is None:
            raise ValueError("human_review resumed without pause state")
        return pause.stage

    def _run_staged_plan(
        self,
        request: PlannerRequest,
        *,
        thread_id: str | None,
        attempts: list[PlannerDebugAttempt],
    ) -> PlannerResult:
        evidence_outcome = self._run_evidence_stage(
            request,
            thread_id=thread_id,
            attempts=attempts,
            resume_payload=None,
            resume_with_command=False,
        )
        if isinstance(evidence_outcome, PlannerResult):
            return evidence_outcome
        return self._run_dsl_stage(
            request,
            evidence_bundle=evidence_outcome,
            thread_id=thread_id,
            attempts=attempts,
            resume_payload=None,
            validation_feedback=None,
            resume_with_command=False,
        )

    def _resume_pending_stage(
        self,
        request: PlannerRequest,
        *,
        thread_id: str,
        resume_payload: Any,
        attempts: list[PlannerDebugAttempt],
    ) -> PlannerResult:
        pending_state = self._pending_states.pop(thread_id)
        if pending_state.stage == "evidence_agent":
            evidence_outcome = self._run_evidence_stage(
                request,
                thread_id=thread_id,
                attempts=attempts,
                resume_payload=resume_payload,
                resume_with_command=pending_state.resume_with_command,
            )
            if isinstance(evidence_outcome, PlannerResult):
                return evidence_outcome
            return self._run_dsl_stage(
                request,
                evidence_bundle=evidence_outcome,
                thread_id=thread_id,
                attempts=attempts,
                resume_payload=None,
                validation_feedback=None,
                resume_with_command=False,
            )
        return self._run_dsl_stage(
            request,
            evidence_bundle=pending_state.evidence_bundle,
            thread_id=thread_id,
            attempts=attempts,
            resume_payload=resume_payload,
            validation_feedback=pending_state.validation_feedback,
            resume_with_command=pending_state.resume_with_command,
        )

    def _run_evidence_stage(
        self,
        request: PlannerRequest,
        *,
        thread_id: str | None,
        attempts: list[PlannerDebugAttempt],
        resume_payload: Any,
        resume_with_command: bool = False,
    ) -> EvidenceBundle | PlannerResult | PlannerStagePause:
        run_config = self._build_run_config(thread_id)
        if resume_payload is not None and resume_with_command:
            agent_input = Command(resume=resume_payload)
        else:
            agent_input = {
                "messages": [
                    {
                        "role": "user",
                        "content": self._build_evidence_prompt(
                            request,
                            resume_payload=resume_payload,
                        ),
                    }
                ]
            }
        with logger.contextualize(
            planner_thread_id=thread_id or "-",
            planner_round="evidence_agent",
            planner_input_mode="resume" if resume_payload is not None else "prompt",
        ):
            logger.bind(
                planner_event="evidence_stage_start",
                planner_input_snapshot=self._snapshot_request_input(agent_input),
            ).info("planner evidence_agent stage started")
            with activate_planner_runtime_guard() as runtime_guard:
                try:
                    raw_response = self.evidence_agent.invoke(agent_input, config=run_config)
                except ToolCallLimitExceededError as exc:
                    runtime_guard.record_tool_budget_exhausted(
                        tool_name=exc.tool_name,
                        run_limit=exc.run_limit,
                        run_count=exc.run_count,
                    )
                    self._append_debug_attempt(
                        request,
                        attempts=attempts,
                        round_index=1,
                        raw_response={
                            "error": {
                                "type": exc.__class__.__name__,
                                "message": str(exc),
                            }
                        },
                        repair_feedback=None,
                        phase="evidence_agent",
                    )
                    logger.bind(
                        planner_event="evidence_stage_tool_budget_exhausted",
                        planner_error_type=exc.__class__.__name__,
                        planner_error_detail=self._build_exception_log_payload(exc),
                        planner_traceback=traceback.format_exc(),
                    ).warning("planner evidence_agent stage stopped after exceeding tool budget")
                    return self._build_tool_budget_exhausted_result(
                        request,
                        attempts=attempts,
                        runtime_guard=runtime_guard,
                        failure_stage="runtime_guard",
                        failure_message=str(exc),
                        error_message=str(exc),
                    )
                except Exception as exc:
                    logger.bind(
                        planner_event="evidence_stage_error",
                        planner_error_type=exc.__class__.__name__,
                        planner_error_detail=self._build_exception_log_payload(exc),
                        planner_traceback=traceback.format_exc(),
                    ).error("planner evidence_agent stage failed during agent invoke")
                    return PlannerResult(
                        status="blocked",
                        reason="agent_error",
                        error=PlannerError(type=exc.__class__.__name__, message=str(exc)),
                        debug=self._build_debug_info(
                            request,
                            attempts=attempts,
                            failure_stage="agent_error",
                            failure_message=str(exc),
                            guard_events=runtime_guard.events,
                        ),
                    )

                logger.bind(
                    planner_event="evidence_stage_response",
                    planner_response_type=type(raw_response).__name__,
                    planner_response_snapshot=self._snapshot_response(raw_response),
                ).info("planner evidence_agent stage returned a response")
                self._append_debug_attempt(
                    request,
                    attempts=attempts,
                    round_index=1,
                    raw_response=raw_response,
                    repair_feedback=None,
                    phase="evidence_agent",
                )

                interrupt_result = self._coerce_interrupt_result(raw_response, thread_id=thread_id)
                if interrupt_result is not None:
                    return PlannerStagePause(
                        stage="evidence_agent",
                        questions=interrupt_result.questions,
                        missing_info=interrupt_result.missing_info,
                        assumptions=[],
                        reason="human_review",
                        resume_with_command=True,
                        debug=self._build_debug_info(
                            request,
                            attempts=attempts,
                            failure_stage="human_review",
                            failure_message="planner evidence_agent paused for human review",
                            guard_events=runtime_guard.events,
                        ),
                    )

                try:
                    evidence_result = self._coerce_evidence_result(raw_response)
                except PydanticValidationError:
                    # Backward-compatible fallback for existing single-agent tests and callers.
                    candidate_result = self._coerce_planner_result(raw_response)
                    if candidate_result.status == "needs_human":
                        return PlannerStagePause(
                            stage="evidence_agent",
                            questions=candidate_result.questions,
                            missing_info=candidate_result.missing_info,
                            assumptions=candidate_result.assumptions,
                            reason=candidate_result.reason or "needs_human",
                            debug=self._build_debug_info(
                                request,
                                attempts=attempts,
                                failure_stage="human_review",
                                failure_message="planner evidence_agent paused for human review",
                                guard_events=runtime_guard.events,
                            ),
                        )
                    candidate_result.debug = self._build_debug_info(
                        request,
                        attempts=attempts,
                        guard_events=runtime_guard.events,
                    )
                    return candidate_result

                if evidence_result.status == "blocked":
                    blocked = PlannerResult(
                        status="blocked",
                        reason=evidence_result.reason or "evidence_blocked",
                        error=evidence_result.error,
                        debug=self._build_debug_info(
                            request,
                            attempts=attempts,
                            failure_stage="agent_error",
                            failure_message=evidence_result.error.message if evidence_result.error else None,
                            guard_events=runtime_guard.events,
                        ),
                    )
                    return blocked
                if evidence_result.status == "needs_human":
                    return PlannerStagePause(
                        stage="evidence_agent",
                        questions=evidence_result.questions,
                        missing_info=evidence_result.missing_info,
                        assumptions=evidence_result.assumptions,
                        reason=evidence_result.reason or "needs_human",
                        debug=self._build_debug_info(
                            request,
                            attempts=attempts,
                            failure_stage="human_review",
                            failure_message="planner evidence_agent paused for human review",
                            guard_events=runtime_guard.events,
                        ),
                    )

                evidence_result.evidence_bundle.assumptions = list(
                    dict.fromkeys(
                        [*evidence_result.evidence_bundle.assumptions, *evidence_result.assumptions]
                    )
                )
                return evidence_result.evidence_bundle

    def _run_dsl_stage(
        self,
        request: PlannerRequest,
        *,
        evidence_bundle: EvidenceBundle | None,
        thread_id: str | None,
        attempts: list[PlannerDebugAttempt],
        resume_payload: Any,
        validation_feedback: str | None,
        resume_with_command: bool = False,
    ) -> PlannerResult | PlannerStagePause:
        run_config = self._build_run_config(thread_id)
        current_feedback = validation_feedback
        last_validation_error: Exception | None = None

        for round_index in range(1, self.config.max_planning_rounds + 1):
            if resume_payload is not None and resume_with_command:
                agent_input = Command(resume=resume_payload)
            else:
                agent_input = {
                    "messages": [
                        {
                            "role": "user",
                            "content": self._build_dsl_prompt(
                                request,
                                evidence_bundle=evidence_bundle,
                                validation_feedback=current_feedback,
                                resume_payload=resume_payload,
                            ),
                        }
                    ]
                }
            with logger.contextualize(
                planner_thread_id=thread_id or "-",
                planner_round=f"dsl_agent.{round_index}",
                planner_input_mode="resume" if resume_payload is not None else "prompt",
            ):
                logger.bind(
                    planner_event="dsl_stage_start",
                    planner_round_index=round_index,
                    planner_input_snapshot=self._snapshot_request_input(agent_input),
                    planner_validation_feedback=serialize_for_log(current_feedback),
                ).info("planner dsl_agent stage started")
                with activate_planner_runtime_guard() as runtime_guard:
                    try:
                        raw_response = self.dsl_agent.invoke(agent_input, config=run_config)
                    except ToolCallLimitExceededError as exc:
                        runtime_guard.record_tool_budget_exhausted(
                            tool_name=exc.tool_name,
                            run_limit=exc.run_limit,
                            run_count=exc.run_count,
                        )
                        self._append_debug_attempt(
                            request,
                            attempts=attempts,
                            round_index=round_index,
                            raw_response={
                                "error": {
                                    "type": exc.__class__.__name__,
                                    "message": str(exc),
                                }
                            },
                            repair_feedback=current_feedback,
                            phase="dsl_agent",
                        )
                        logger.bind(
                            planner_event="dsl_stage_tool_budget_exhausted",
                            planner_round_index=round_index,
                            planner_error_type=exc.__class__.__name__,
                            planner_error_detail=self._build_exception_log_payload(exc),
                            planner_traceback=traceback.format_exc(),
                        ).warning("planner dsl_agent stage stopped after exceeding tool budget")
                        return self._force_finalize_after_tool_budget(
                            request,
                            validation_feedback=current_feedback,
                            tool_budget_error=exc,
                            round_index=round_index,
                            run_config=run_config,
                            attempts=attempts,
                            runtime_guard=runtime_guard,
                        )
                    except Exception as exc:
                        logger.bind(
                            planner_event="dsl_stage_error",
                            planner_round_index=round_index,
                            planner_error_type=exc.__class__.__name__,
                            planner_error_detail=self._build_exception_log_payload(exc),
                            planner_traceback=traceback.format_exc(),
                        ).error("planner dsl_agent stage failed during agent invoke")
                        return PlannerResult(
                            status="blocked",
                            reason="agent_error",
                            error=PlannerError(type=exc.__class__.__name__, message=str(exc)),
                            debug=self._build_debug_info(
                                request,
                                attempts=attempts,
                                failure_stage="agent_error",
                                failure_message=str(exc),
                                guard_events=runtime_guard.events,
                            ),
                        )

                    logger.bind(
                        planner_event="dsl_stage_response",
                        planner_round_index=round_index,
                        planner_response_type=type(raw_response).__name__,
                        planner_response_snapshot=self._snapshot_response(raw_response),
                    ).info("planner dsl_agent stage returned a response")
                    self._append_debug_attempt(
                        request,
                        attempts=attempts,
                        round_index=round_index,
                        raw_response=raw_response,
                        repair_feedback=current_feedback,
                        phase="dsl_agent",
                    )

                    interrupt_result = self._coerce_interrupt_result(raw_response, thread_id=thread_id)
                    if interrupt_result is not None:
                        return PlannerStagePause(
                            stage="dsl_agent",
                            questions=interrupt_result.questions,
                            missing_info=interrupt_result.missing_info,
                            assumptions=[],
                            reason="human_review",
                            evidence_bundle=evidence_bundle,
                            validation_feedback=current_feedback,
                            resume_with_command=True,
                            debug=self._build_debug_info(
                                request,
                                attempts=attempts,
                                failure_stage="human_review",
                                failure_message="planner dsl_agent paused for human review",
                                guard_events=runtime_guard.events,
                            ),
                        )

                    try:
                        candidate_result = self._coerce_planner_result(raw_response)
                        if candidate_result.status == "ready":
                            self._validate_ready_task_document(candidate_result.task_document)
                        if candidate_result.status == "needs_human":
                            return PlannerStagePause(
                                stage="dsl_agent",
                                questions=candidate_result.questions,
                                missing_info=candidate_result.missing_info,
                                assumptions=candidate_result.assumptions,
                                reason=candidate_result.reason or "needs_human",
                                evidence_bundle=evidence_bundle,
                                validation_feedback=current_feedback,
                                debug=self._build_debug_info(
                                    request,
                                    attempts=attempts,
                                    failure_stage="human_review",
                                    failure_message="planner dsl_agent paused for human review",
                                    guard_events=runtime_guard.events,
                                ),
                            )
                        candidate_result.debug = self._build_debug_info(
                            request,
                            attempts=attempts,
                            guard_events=runtime_guard.events,
                        )
                        return candidate_result
                    except (PydanticValidationError, ValidationError, DiceError, ValueError, TypeError) as exc:
                        last_validation_error = exc
                        if attempts:
                            attempts[-1].validation_error = str(exc)
                        current_feedback = (
                            "Your previous structured output was invalid. "
                            f"Repair it so it satisfies the schema and engine constraints: {exc}"
                        )
                        logger.bind(
                            planner_event="dsl_stage_validation_failed",
                            planner_round_index=round_index,
                            planner_validation_error=str(exc),
                            planner_validation_feedback=current_feedback,
                        ).warning("planner dsl_agent stage produced an invalid structured result")
                        resume_payload = None

        message = str(last_validation_error or "planner output repair budget exhausted")
        result = PlannerResult(
            status="needs_human",
            questions=[
                PlannerQuestion(
                    question="当前 DSL 规划阶段未能产出合法 TaskDocument。请检查调试信息，必要时再补充动作细节。",
                    missing_info="task_document_validation",
                    why=message,
                )
            ],
            missing_info=["task_document_validation"],
            reason="task_document_validation",
            error=PlannerError(
                type=last_validation_error.__class__.__name__ if last_validation_error else "planner_validation_error",
                message=message,
            ),
            debug=self._build_debug_info(
                request,
                attempts=attempts,
                failure_stage="schema_or_semantic_validation",
                failure_message=message,
            ),
        )
        logger.bind(
            planner_event="repair_budget_exhausted",
            planner_error_type=result.error.type if result.error else "planner_validation_error",
            planner_error_message=message,
        ).warning("planner exhausted its repair budget")
        return result

    def _store_pending_needs_human(
        self,
        request: PlannerRequest,
        *,
        thread_id: str | None,
        stage: Literal["evidence_agent", "dsl_agent"],
        questions: list[PlannerQuestion],
        missing_info: list[str],
        assumptions: list[str],
        reason: str,
        evidence_bundle: EvidenceBundle | None,
        validation_feedback: str | None,
        resume_with_command: bool,
        attempts: list[PlannerDebugAttempt],
        guard_events: list[PlannerGuardEvent],
    ) -> PlannerResult:
        if thread_id:
            self._pending_states[thread_id] = PendingPlannerState(
                stage=stage,
                evidence_bundle=evidence_bundle,
                validation_feedback=validation_feedback,
                resume_with_command=resume_with_command,
            )
        result = PlannerResult(
            status="needs_human",
            questions=questions,
            missing_info=missing_info,
            assumptions=assumptions,
            reason=reason,
            resume=PlannerResumeToken(thread_id=thread_id) if thread_id else None,
            debug=self._build_debug_info(
                request,
                attempts=attempts,
                failure_stage="human_review",
                failure_message=f"planner paused in {stage}",
                guard_events=guard_events,
            ),
        )
        return result

    def _coerce_interrupt_result(
        self,
        raw_response: Any,
        *,
        thread_id: str | None,
    ) -> PlannerResult | None:
        if not isinstance(raw_response, dict) or "__interrupt__" not in raw_response:
            return None
        questions = self._build_interrupt_questions(raw_response["__interrupt__"])
        if not questions:
            questions = [
                PlannerQuestion(
                    question="规划流程在等待人工审批或补充决策。",
                    missing_info="human_review",
                    why="planner run was interrupted and requires resume input",
                )
            ]
        return PlannerResult(
            status="needs_human",
            questions=questions,
            missing_info=["human_review"],
            assumptions=[],
            resume=PlannerResumeToken(thread_id=thread_id) if thread_id else None,
        )

    def _validate_ready_task_document(self, document: dict[str, Any] | None) -> None:
        validate_candidate_task_document(document)

    def _build_agent_input(
        self,
        request: PlannerRequest,
        *,
        validation_feedback: str | None,
    ) -> Any:
        if request.resume is not None:
            return Command(resume=request.resume)
        return {
            "messages": [
                {
                    "role": "user",
                    "content": self._build_user_prompt(
                        request,
                        validation_feedback=validation_feedback,
                    ),
                }
            ]
        }

    def _build_run_config(self, thread_id: str | None) -> dict[str, Any] | None:
        if thread_id is None:
            return None
        return {"configurable": {"thread_id": thread_id}}

    def _resolve_thread_id(self, request: PlannerRequest) -> str | None:
        if request.resume is not None:
            return request.thread_id
        return uuid4().hex

    def _build_interrupt_questions(self, interrupts: Any) -> list[PlannerQuestion]:
        questions: list[PlannerQuestion] = []
        for interrupt in interrupts if isinstance(interrupts, list | tuple) else [interrupts]:
            payload = getattr(interrupt, "value", interrupt)
            if not isinstance(payload, dict):
                if payload is not None:
                    questions.append(
                        PlannerQuestion(
                            question=str(payload),
                            missing_info="human_review",
                            why="planner run was interrupted",
                        )
                    )
                continue

            action_requests = payload.get("action_requests")
            review_configs = payload.get("review_configs")
            if not isinstance(action_requests, list):
                questions.append(
                    PlannerQuestion(
                        question=str(payload),
                        missing_info="human_review",
                        why="planner run was interrupted",
                    )
                )
                continue

            for index, action_request in enumerate(action_requests):
                if not isinstance(action_request, dict):
                    continue
                description = action_request.get("description") or (
                    f"Please review tool call {action_request.get('name', 'unknown')}."
                )
                options: list[str] = []
                if isinstance(review_configs, list) and index < len(review_configs):
                    review_config = review_configs[index]
                    if isinstance(review_config, dict):
                        allowed = review_config.get("allowed_decisions")
                        if isinstance(allowed, list):
                            options = [str(item) for item in allowed]
                questions.append(
                    PlannerQuestion(
                        question=str(description),
                        missing_info="human_review",
                        why=f"Pending review for tool {action_request.get('name', 'unknown')}",
                        options=options,
                    )
                )
        return questions

    def _append_debug_attempt(
        self,
        request: PlannerRequest,
        *,
        attempts: list[PlannerDebugAttempt],
        round_index: int,
        raw_response: Any,
        repair_feedback: str | None,
        phase: Literal["planning", "forced_finalize", "evidence_agent", "dsl_agent"] = "planning",
    ) -> None:
        if not request.debug:
            return
        attempts.append(
            PlannerDebugAttempt(
                round=round_index,
                input_mode="resume" if request.resume is not None else "prompt",
                phase=phase,
                response_snapshot=self._snapshot_response(raw_response),
                repair_feedback=repair_feedback,
            )
        )

    def _build_debug_info(
        self,
        request: PlannerRequest,
        *,
        attempts: list[PlannerDebugAttempt],
        failure_stage: Literal[
            "human_review",
            "agent_error",
            "schema_or_semantic_validation",
            "runtime_guard",
            "forced_finalize",
        ] | None = None,
        failure_message: str | None = None,
        guard_events: list[PlannerGuardEvent] | None = None,
    ) -> PlannerDebugInfo | None:
        if not request.debug:
            return None
        return PlannerDebugInfo(
            attempts=list(attempts),
            failure_stage=failure_stage,
            failure_message=failure_message,
            guard_events=list(guard_events or []),
        )

    def _force_finalize_after_tool_budget(
        self,
        request: PlannerRequest,
        *,
        validation_feedback: str | None,
        tool_budget_error: ToolCallLimitExceededError,
        round_index: int,
        run_config: dict[str, Any] | None,
        attempts: list[PlannerDebugAttempt],
        runtime_guard: Any,
    ) -> PlannerResult:
        feedback = self._build_forced_finalize_feedback(
            validation_feedback=validation_feedback,
            tool_budget_error=tool_budget_error,
        )
        agent_input = {
            "messages": [
                {
                    "role": "user",
                    "content": self._build_user_prompt(
                        request,
                        validation_feedback=feedback,
                    ),
                }
            ]
        }
        logger.bind(
            planner_event="forced_finalize_start",
            planner_round_index=round_index,
            planner_input_snapshot=self._snapshot_request_input(agent_input),
        ).info("planner forced finalize started after tool budget exhaustion")
        try:
            raw_response = self._get_forced_finalize_agent().invoke(agent_input, config=run_config)
        except Exception as exc:
            logger.bind(
                planner_event="forced_finalize_error",
                planner_round_index=round_index,
                planner_error_type=exc.__class__.__name__,
                planner_error_detail=self._build_exception_log_payload(exc),
                planner_traceback=traceback.format_exc(),
            ).error("planner forced finalize failed during agent invoke")
            return PlannerResult(
                status="blocked",
                reason="agent_error",
                error=PlannerError(type=exc.__class__.__name__, message=str(exc)),
                debug=self._build_debug_info(
                    request,
                    attempts=attempts,
                    failure_stage="forced_finalize",
                    failure_message=str(exc),
                    guard_events=runtime_guard.events,
                ),
            )

        logger.bind(
            planner_event="forced_finalize_response",
            planner_round_index=round_index,
            planner_response_type=type(raw_response).__name__,
            planner_response_snapshot=self._snapshot_response(raw_response),
        ).info("planner forced finalize returned a response")
        self._append_debug_attempt(
            request,
            attempts=attempts,
            round_index=round_index,
            raw_response=raw_response,
            repair_feedback=feedback,
            phase="forced_finalize",
        )

        try:
            candidate_result = self._coerce_planner_result(raw_response)
            if candidate_result.status == "ready":
                self._validate_ready_task_document(candidate_result.task_document)
            if self._is_budget_echo_result(candidate_result):
                raise ValueError("forced finalize repeated tool budget exhaustion instead of producing a final outcome")
            candidate_result.debug = self._build_debug_info(
                request,
                attempts=attempts,
                guard_events=runtime_guard.events,
            )
            logger.bind(
                planner_event="forced_finalize_result",
                planner_round_index=round_index,
                planner_status=candidate_result.status,
                planner_reason=candidate_result.reason,
            ).info("planner forced finalize produced a valid result")
            return candidate_result
        except (PydanticValidationError, ValidationError, DiceError, ValueError, TypeError) as exc:
            if attempts:
                attempts[-1].validation_error = str(exc)
            logger.bind(
                planner_event="forced_finalize_invalid",
                planner_round_index=round_index,
                planner_validation_error=str(exc),
            ).warning("planner forced finalize produced an invalid structured result")
            failure_message = (
                f"{tool_budget_error} Forced finalize failed to produce a valid PlannerResult: {exc}"
            )
            return self._build_tool_budget_exhausted_result(
                request,
                attempts=attempts,
                runtime_guard=runtime_guard,
                failure_stage="forced_finalize",
                failure_message=failure_message,
                error_message=failure_message,
            )

    def _build_tool_budget_exhausted_result(
        self,
        request: PlannerRequest,
        *,
        attempts: list[PlannerDebugAttempt],
        runtime_guard: Any,
        failure_stage: Literal["runtime_guard", "forced_finalize"],
        failure_message: str,
        error_message: str,
    ) -> PlannerResult:
        missing_info = build_guard_missing_info(runtime_guard) or ["planner_tool_budget"]
        return PlannerResult(
            status="needs_human",
            questions=[
                PlannerQuestion(
                    question="当前规划在工具预算内仍未收敛。请确认缺失事实、补充关键状态，或缩小动作范围后重试。",
                    missing_info="planner_tool_budget",
                    why=failure_message,
                )
            ],
            missing_info=missing_info,
            assumptions=[],
            reason="tool_budget_exhausted",
            error=PlannerError(type="ToolCallLimitExceededError", message=error_message),
            debug=self._build_debug_info(
                request,
                attempts=attempts,
                failure_stage=failure_stage,
                failure_message=failure_message,
                guard_events=runtime_guard.events,
            ),
        )

    def _build_forced_finalize_feedback(
        self,
        *,
        validation_feedback: str | None,
        tool_budget_error: ToolCallLimitExceededError,
    ) -> str:
        forced_finalize_feedback = (
            "Forced finalize: the planner has exhausted its tool budget. "
            "Do not call any tools. Do not ask for more tool use. "
            "Based only on the evidence already gathered in this run, return your best final PlannerResult. "
            "If the evidence is sufficient, return status ready with a valid task_document. "
            "If the evidence is insufficient, return status needs_human with concrete questions and missing_info. "
            f"Original tool budget error: {tool_budget_error}"
        )
        if validation_feedback:
            return f"{validation_feedback}\n\n{forced_finalize_feedback}"
        return forced_finalize_feedback

    def _is_budget_echo_result(self, result: PlannerResult) -> bool:
        reason = (result.reason or "").lower()
        error_type = (result.error.type if result.error else "").lower()
        error_message = (result.error.message if result.error else "").lower()
        budget_markers = ("tool_budget", "tool budget", "tool call limit", "toolcalllimit")
        if any(marker in reason for marker in budget_markers):
            return True
        if any(marker in error_type for marker in budget_markers):
            return True
        if any(marker in error_message for marker in budget_markers):
            return True
        if result.status == "needs_human" and result.missing_info and all(
            item == "planner_tool_budget" for item in result.missing_info
        ):
            return True
        return False

    def _get_forced_finalize_agent(self) -> Any:
        if self._forced_finalize_agent is None:
            if self._forced_finalize_agent_factory is None:
                raise RuntimeError("forced finalize agent is unavailable")
            self._forced_finalize_agent = self._forced_finalize_agent_factory()
        return self._forced_finalize_agent

    def _snapshot_response(self, raw_response: Any) -> Any:
        payload = raw_response
        if isinstance(raw_response, BaseModel):
            payload = raw_response.model_dump(exclude_none=True)
        if isinstance(payload, dict):
            if "structured_response" in payload:
                nested = payload["structured_response"]
                if isinstance(nested, BaseModel):
                    return nested.model_dump(exclude_none=True)
                return nested
            if "__interrupt__" in payload:
                return {
                    "__interrupt__": [
                        getattr(interrupt, "value", interrupt)
                        for interrupt in payload["__interrupt__"]
                    ]
                }
        return payload

    def _build_user_prompt(
        self,
        request: PlannerRequest,
        *,
        validation_feedback: str | None,
    ) -> str:
        return _render_prompt_template(
            self.config.user_prompt_template,
            {
                "instruction": request.instruction,
                "context_json": json.dumps(request.context, ensure_ascii=False, sort_keys=True),
                "policy_json": json.dumps(request.policy, ensure_ascii=False, sort_keys=True),
                "tool_budget": str(self.config.tool_budget),
                "validation_feedback": validation_feedback or "",
            },
            template_kind="planner user prompt",
        )

    def _build_evidence_prompt(
        self,
        request: PlannerRequest,
        *,
        resume_payload: Any,
    ) -> str:
        base_prompt = self._build_user_prompt(request, validation_feedback="")
        parts = [
            "Stage: evidence_agent.",
            "Your job in this stage is to gather evidence only.",
            "Do not draft or repair a TaskDocument in this stage.",
            "Use only search, list, and read to collect enough information for the DSL stage.",
            "Return status ready with an evidence_bundle when the evidence is sufficient for dsl_agent.",
            "Return status needs_human with concrete questions when more human input is required.",
            "Return status blocked only for genuine system failures.",
            "",
            "EvidenceBundle must be lightweight and include:",
            "- summary",
            "- facts[] with name, value_summary, source_paths, source_kind, optional note",
            "- missing_info",
            "- assumptions",
            "- ready_for_dsl",
        ]
        if resume_payload is not None:
            parts.extend(
                [
                    "",
                    "Human resume payload for this stage:",
                    json.dumps(resume_payload, ensure_ascii=False, sort_keys=True),
                ]
            )
        parts.extend(["", base_prompt])
        return "\n".join(parts)

    def _build_dsl_prompt(
        self,
        request: PlannerRequest,
        *,
        evidence_bundle: EvidenceBundle | None,
        validation_feedback: str | None,
        resume_payload: Any,
    ) -> str:
        base_prompt = self._build_user_prompt(request, validation_feedback=validation_feedback)
        parts = [
            "Stage: dsl_agent.",
            "Your job in this stage is to draft or repair a TaskDocument from the provided EvidenceBundle.",
            "Do not use search, list, or read in this stage.",
            "Use lint to validate and iteratively improve the candidate TaskDocument.",
            "Only return status blocked for genuine system failures, not merely because earlier evidence gathering was hard.",
            "",
            "EvidenceBundle:",
            self._render_evidence_bundle(evidence_bundle),
        ]
        if resume_payload is not None:
            parts.extend(
                [
                    "",
                    "Human resume payload for this stage:",
                    json.dumps(resume_payload, ensure_ascii=False, sort_keys=True),
                ]
            )
        parts.extend(["", base_prompt])
        return "\n".join(parts)

    def _render_evidence_bundle(self, evidence_bundle: EvidenceBundle | None) -> str:
        if evidence_bundle is None:
            return "(missing)"
        payload = evidence_bundle.model_dump(exclude_none=True)
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)

    def _snapshot_request_input(self, agent_input: Any) -> Any:
        if isinstance(agent_input, Command):
            return {"resume": serialize_for_log(getattr(agent_input, "resume", None))}
        if isinstance(agent_input, dict):
            return serialize_for_log(agent_input)
        return serialize_for_log(agent_input)

    def _build_exception_log_payload(self, exc: Exception) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": exc.__class__.__name__,
            "message": str(exc),
        }
        if isinstance(exc, StructuredOutputValidationError):
            payload["tool_name"] = exc.tool_name
            payload["source"] = serialize_for_log(str(exc.source))
            payload["ai_message"] = summarize_ai_message(exc.ai_message)
        else:
            source = getattr(exc, "source", None)
            if source is not None:
                payload["source"] = serialize_for_log(str(source))
            ai_message = getattr(exc, "ai_message", None)
            if ai_message is not None:
                payload["ai_message"] = summarize_ai_message(ai_message)
        return payload


def create_planner(
    *,
    model: Any = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
    interrupt_on: dict[str, Any] | None = None,
    max_planning_rounds: int | None = None,
    tool_budget: int | None = None,
    system_prompt_template: str | None = None,
    user_prompt_template: str | None = None,
    project_config: ProjectConfig | None = None,
    config_path: str | None = None,
    search_tool: SearchTool | None = None,
    list_tool: ListTool | None = None,
    fetch_keys_tool: FetchKeysTool | None = None,
    read_tool: ReadTool | None = None,
    reads_tool: ReadsTool | None = None,
    lint_tool: LintTool | None = None,
    state: Any | None = None,
    state_provider: Callable[[], Any] | None = None,
    checkpointer: Any | None = None,
    model_builder: Callable[[PlannerFactoryConfig], Any] | None = None,
    agent_factory: Callable[..., Any] | None = None,
) -> Planner:
    resolved_project_config = project_config
    if resolved_project_config is None and (
        search_tool is None
        or any(
            value is None
            for value in (
                model,
                base_url,
                api_key,
                timeout,
                max_retries,
                interrupt_on,
                max_planning_rounds,
                tool_budget,
                system_prompt_template,
                user_prompt_template,
            )
        )
    ):
        resolved_project_config = load_project_config(config_path)
    config = resolve_planner_factory_config(
        model=model,
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
        max_retries=max_retries,
        interrupt_on=interrupt_on,
        max_planning_rounds=max_planning_rounds,
        tool_budget=tool_budget,
        system_prompt_template=system_prompt_template,
        user_prompt_template=user_prompt_template,
        project_config=resolved_project_config,
        config_path=config_path,
    )
    if search_tool is None and resolved_project_config is None:
        raise ValueError("project_config or config_path is required when search_tool is not provided")
    search = search_tool or create_search_tool(project_config=resolved_project_config, config_path=config_path)
    resolved_list_tool = list_tool or fetch_keys_tool or create_list_tool(state=state, state_provider=state_provider)
    resolved_read_tool = read_tool or reads_tool or create_read_tool(state=state, state_provider=state_provider)
    lint = lint_tool or create_lint_tool()
    resolved_model = (model_builder or build_planner_model)(config)
    project_root = resolve_project_root(config_path)
    resolved_agent_factory = agent_factory or _load_default_agent_factory()
    resolved_checkpointer = _resolve_checkpointer(config, checkpointer)
    evidence_agent = resolved_agent_factory(
        model=resolved_model,
        tools=[search, resolved_list_tool, resolved_read_tool],
        system_prompt=_build_system_prompt(config),
        response_format=ToolStrategy(EvidenceAgentResult),
        tool_budget=config.tool_budget,
        checkpointer=resolved_checkpointer,
        interrupt_on=config.interrupt_on or None,
    )
    dsl_agent = resolved_agent_factory(
        model=resolved_model,
        tools=[lint],
        system_prompt=_build_system_prompt(config),
        response_format=ToolStrategy(PlannerResult),
        tool_budget=config.tool_budget,
        checkpointer=resolved_checkpointer,
        interrupt_on=config.interrupt_on or None,
    )

    def build_forced_finalize_agent() -> Any:
        return resolved_agent_factory(
            model=resolved_model,
            tools=[],
            system_prompt=_build_system_prompt(config),
            response_format=ToolStrategy(PlannerResult),
            tool_budget=1,
            checkpointer=None,
            interrupt_on=None,
        )

    return Planner(
        evidence_agent=evidence_agent,
        dsl_agent=dsl_agent,
        config=config,
        project_root=project_root,
        search_tool=search,
        list_tool=resolved_list_tool,
        read_tool=resolved_read_tool,
        lint_tool=lint,
        forced_finalize_agent_factory=build_forced_finalize_agent,
        graph_checkpointer=resolved_checkpointer,
    )


def resolve_planner_factory_config(
    *,
    model: Any = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
    interrupt_on: dict[str, Any] | None = None,
    max_planning_rounds: int | None = None,
    tool_budget: int | None = None,
    system_prompt_template: str | None = None,
    user_prompt_template: str | None = None,
    project_config: ProjectConfig | None = None,
    config_path: str | None = None,
) -> PlannerFactoryConfig:
    resolved_project_config = project_config
    planner_defaults = None
    if any(
        value is None
        for value in (
            model,
            base_url,
            api_key,
            timeout,
            max_retries,
            interrupt_on,
            max_planning_rounds,
            tool_budget,
            system_prompt_template,
            user_prompt_template,
        )
    ):
        resolved_project_config = resolved_project_config or load_project_config(config_path)
        planner_defaults = resolved_project_config.planner
    return PlannerFactoryConfig(
        model=model if model is not None else planner_defaults.model,
        base_url=base_url if base_url is not None else planner_defaults.base_url,
        api_key=api_key if api_key is not None else planner_defaults.api_key,
        timeout=timeout if timeout is not None else planner_defaults.timeout,
        max_retries=max_retries if max_retries is not None else planner_defaults.max_retries,
        interrupt_on=interrupt_on if interrupt_on is not None else dict(planner_defaults.interrupt_on),
        max_planning_rounds=(
            max_planning_rounds if max_planning_rounds is not None else planner_defaults.max_planning_rounds
        ),
        tool_budget=tool_budget if tool_budget is not None else planner_defaults.tool_budget,
        system_prompt_template=(
            system_prompt_template
            if system_prompt_template is not None
            else _load_planner_prompt_template(
                project_config=resolved_project_config,
                config_path=config_path,
                file_name=resolved_project_config.planner.prompt.system_file,
                template_kind="planner system prompt",
            )
        ),
        user_prompt_template=(
            user_prompt_template
            if user_prompt_template is not None
            else _load_planner_prompt_template(
                project_config=resolved_project_config,
                config_path=config_path,
                file_name=resolved_project_config.planner.prompt.user_file,
                template_kind="planner user prompt",
            )
        ),
    )


def build_planner_model(config: PlannerFactoryConfig) -> Any:
    if not isinstance(config.model, str):
        return config.model
    provider, model_name = _split_model_spec(config.model)
    kwargs: dict[str, Any] = {
        "timeout": config.timeout,
        "max_retries": config.max_retries,
    }
    if config.base_url is not None or config.api_key is not None:
        if provider != "openai":
            raise ValueError("Custom base_url/api_key is currently only supported for openai models")
        kwargs["base_url"] = config.base_url
        kwargs["api_key"] = config.api_key
    return init_chat_model(model=model_name, model_provider=provider, **kwargs)


def _resolve_checkpointer(config: PlannerFactoryConfig, checkpointer: Any | None) -> Any | None:
    if checkpointer is not None:
        return checkpointer
    memory_mod = importlib.import_module("langgraph.checkpoint.memory")
    saver_cls = getattr(memory_mod, "MemorySaver", None) or getattr(memory_mod, "InMemorySaver", None)
    if saver_cls is None:
        raise RuntimeError("langgraph checkpoint memory saver is unavailable")
    return saver_cls()


def _load_default_agent_factory() -> Callable[..., Any]:
    return _create_default_agent


def _create_default_agent(
    *,
    model: Any,
    tools: list[Any],
    system_prompt: str,
    response_format: Any,
    tool_budget: int,
    checkpointer: Any | None = None,
    interrupt_on: dict[str, Any] | None = None,
) -> Any:
    middleware: list[Any] = [
        ToolCallLimitMiddleware(run_limit=tool_budget, exit_behavior="error"),
    ]
    if interrupt_on:
        middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=middleware,
        response_format=response_format,
        checkpointer=checkpointer,
    )


def _build_system_prompt(config: PlannerFactoryConfig) -> str:
    return _render_prompt_template(
        config.system_prompt_template,
        {"tool_budget": str(config.tool_budget)},
        template_kind="planner system prompt",
    )


def _split_model_spec(model: str) -> tuple[str, str]:
    provider, separator, model_name = model.partition(":")
    if not separator:
        return "openai", model
    if not provider or not model_name:
        raise ValueError(f"Invalid model spec {model!r}")
    return provider, model_name


_PROMPT_PLACEHOLDER_PATTERN = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


def _load_planner_prompt_template(
    *,
    project_config: ProjectConfig,
    config_path: str | None,
    file_name: str,
    template_kind: str,
) -> str:
    prompt_dir = resolve_path_from_config(project_config.planner.prompt.directory, config_path=config_path)
    prompt_path = resolve_path_from_config(
        str(prompt_dir / file_name),
        config_path=config_path,
    )
    try:
        return prompt_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"{template_kind} file was not found: {prompt_path}") from exc
    except OSError as exc:
        raise ValueError(f"Failed to read {template_kind} file {prompt_path}: {exc}") from exc


def _render_prompt_template(
    template: str,
    values: dict[str, str],
    *,
    template_kind: str,
) -> str:
    unknown = sorted({name for name in _PROMPT_PLACEHOLDER_PATTERN.findall(template) if name not in values})
    if unknown:
        raise ValueError(f"{template_kind} contains unsupported placeholders: {', '.join(unknown)}")

    rendered = template
    for key, value in values.items():
        rendered = re.sub(r"{{\s*" + re.escape(key) + r"\s*}}", value, rendered)

    remaining = sorted(set(_PROMPT_PLACEHOLDER_PATTERN.findall(rendered)))
    if remaining:
        raise ValueError(f"{template_kind} still contains unresolved placeholders: {', '.join(remaining)}")
    return rendered
