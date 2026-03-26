from __future__ import annotations

import importlib
import json
import re
from collections.abc import Callable
from typing import Any, Literal
from uuid import uuid4

from langchain.chat_models import init_chat_model
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError, model_validator

from trpg_py.agent.task_document import TASK_DOCUMENT_OUTPUT_SCHEMA, validate_candidate_task_document
from trpg_py.agent.tools import (
    FetchKeysTool,
    LintTool,
    ReadsTool,
    SearchTool,
    create_fetch_keys_tool,
    create_lint_tool,
    create_reads_tool,
    create_search_tool,
)
from trpg_py.config import ProjectConfig, load_project_config, resolve_path_from_config
from trpg_py.errors import ValidationError


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


class PlannerDebugAttempt(BaseModel):
    round: int = Field(ge=1)
    input_mode: Literal["prompt", "resume"]
    response_snapshot: Any = None
    repair_feedback: str | None = None
    validation_error: str | None = None


class PlannerDebugInfo(BaseModel):
    attempts: list[PlannerDebugAttempt] = Field(default_factory=list)
    failure_stage: Literal["human_review", "agent_error", "schema_or_semantic_validation"] | None = None
    failure_message: str | None = None


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


class Planner:
    def __init__(
        self,
        *,
        agent: Any,
        config: PlannerFactoryConfig,
        search_tool: SearchTool,
        fetch_keys_tool: FetchKeysTool,
        reads_tool: ReadsTool,
        lint_tool: LintTool,
    ) -> None:
        self.agent = agent
        self.config = config
        self.search_tool = search_tool
        self.fetch_keys_tool = fetch_keys_tool
        self.reads_tool = reads_tool
        self.lint_tool = lint_tool

    def plan(self, request: PlannerRequest | dict[str, Any]) -> PlannerResult:
        planner_request = PlannerRequest.model_validate(request)
        thread_id = planner_request.thread_id or self._resolve_thread_id(planner_request)
        run_config = self._build_run_config(thread_id)
        validation_feedback: str | None = None
        last_validation_error: Exception | None = None
        debug_attempts: list[PlannerDebugAttempt] = []

        for round_index in range(1, self.config.max_planning_rounds + 1):
            try:
                raw_response = self.agent.invoke(
                    self._build_agent_input(
                        planner_request,
                        validation_feedback=validation_feedback,
                    ),
                    config=run_config,
                )
            except Exception as exc:
                return PlannerResult(
                    status="blocked",
                    reason="agent_error",
                    error=PlannerError(type=exc.__class__.__name__, message=str(exc)),
                    debug=self._build_debug_info(
                        planner_request,
                        attempts=debug_attempts,
                        failure_stage="agent_error",
                        failure_message=str(exc),
                    ),
                )

            self._append_debug_attempt(
                planner_request,
                attempts=debug_attempts,
                round_index=round_index,
                raw_response=raw_response,
                repair_feedback=validation_feedback,
            )

            interrupt_result = self._coerce_interrupt_result(raw_response, thread_id=thread_id)
            if interrupt_result is not None:
                interrupt_result.reason = "human_review"
                interrupt_result.debug = self._build_debug_info(
                    planner_request,
                    attempts=debug_attempts,
                    failure_stage="human_review",
                    failure_message="planner run paused for human review",
                )
                return interrupt_result

            try:
                result = self._coerce_planner_result(raw_response)
                if result.status == "ready":
                    self._validate_ready_task_document(result.task_document)
                result.debug = self._build_debug_info(planner_request, attempts=debug_attempts)
                return result
            except (PydanticValidationError, ValidationError, ValueError) as exc:
                last_validation_error = exc
                if debug_attempts:
                    debug_attempts[-1].validation_error = str(exc)
                validation_feedback = (
                    "Your previous structured output was invalid. "
                    f"Repair it so it satisfies the schema and engine constraints: {exc}"
                )

        message = str(last_validation_error or "planner output repair budget exhausted")
        return PlannerResult(
            status="needs_human",
            questions=[
                PlannerQuestion(
                    question="当前规划流程未能产出合法 TaskDocument。请检查调试信息，必要时再补充动作细节。",
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
                planner_request,
                attempts=debug_attempts,
                failure_stage="schema_or_semantic_validation",
                failure_message=message,
            ),
        )

    def _coerce_planner_result(self, raw_response: Any) -> PlannerResult:
        payload = raw_response
        if isinstance(raw_response, dict) and "structured_response" in raw_response:
            payload = raw_response["structured_response"]
        if isinstance(payload, BaseModel):
            payload = payload.model_dump(exclude_none=True)
        return PlannerResult.model_validate(payload)

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
        if self.config.interrupt_on:
            return uuid4().hex
        return None

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
    ) -> None:
        if not request.debug:
            return
        attempts.append(
            PlannerDebugAttempt(
                round=round_index,
                input_mode="resume" if request.resume is not None else "prompt",
                response_snapshot=self._snapshot_response(raw_response),
                repair_feedback=repair_feedback,
            )
        )

    def _build_debug_info(
        self,
        request: PlannerRequest,
        *,
        attempts: list[PlannerDebugAttempt],
        failure_stage: Literal["human_review", "agent_error", "schema_or_semantic_validation"] | None = None,
        failure_message: str | None = None,
    ) -> PlannerDebugInfo | None:
        if not request.debug:
            return None
        return PlannerDebugInfo(
            attempts=list(attempts),
            failure_stage=failure_stage,
            failure_message=failure_message,
        )

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
    fetch_keys_tool: FetchKeysTool | None = None,
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
    fetch_keys = fetch_keys_tool or create_fetch_keys_tool(state=state, state_provider=state_provider)
    reads = reads_tool or create_reads_tool(state=state, state_provider=state_provider)
    lint = lint_tool or create_lint_tool()
    resolved_model = (model_builder or build_planner_model)(config)
    deep_agent = (agent_factory or _load_default_agent_factory())(
        model=resolved_model,
        tools=[search, fetch_keys, reads, lint],
        system_prompt=_build_system_prompt(config),
        response_format=PlannerResult,
        checkpointer=_resolve_checkpointer(config, checkpointer),
        interrupt_on=config.interrupt_on or None,
    )
    return Planner(
        agent=deep_agent,
        config=config,
        search_tool=search,
        fetch_keys_tool=fetch_keys,
        reads_tool=reads,
        lint_tool=lint,
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
    if not config.interrupt_on:
        return None
    memory_mod = importlib.import_module("langgraph.checkpoint.memory")
    saver_cls = getattr(memory_mod, "MemorySaver", None) or getattr(memory_mod, "InMemorySaver", None)
    if saver_cls is None:
        raise RuntimeError("langgraph checkpoint memory saver is unavailable")
    return saver_cls()


def _load_default_agent_factory() -> Callable[..., Any]:
    try:
        mod = importlib.import_module("deepagents")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "deepagents is not installed. Install project dependencies before creating a planner."
        ) from exc
    factory = getattr(mod, "create_deep_agent", None)
    if factory is None:
        raise RuntimeError("deepagents.create_deep_agent is unavailable")
    return factory


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
