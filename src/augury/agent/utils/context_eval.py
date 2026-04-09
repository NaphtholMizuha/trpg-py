from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from augury.agent.orchestrate import PlannerDependencies, build_context_agent_payload, create_planner
from augury.agent.models import AskRequest, AskResponse, ContextBundle, PlannerRequest
from augury.agent.utils.cli_ask import prompt_for_ask_requests
from augury.agent.utils.state_loader import load_toml_state


DEFAULT_CONTEXT_AGENT_EVAL_INTENT = "Aldera用火球术攻击goblin_1"
DEFAULT_CONTEXT_AGENT_EVAL_STATE_FILE = (
    Path(__file__).resolve().parents[4] / "examples" / "evals" / "planner_e2e" / "world_state.toml"
)


@dataclass(slots=True)
class ContextAgentEvalResult:
    payload: dict[str, Any]
    bundle: ContextBundle
    state_file: Path
    ask_interaction: str = "not_needed"
    ask_interaction_message: str | None = None
    interrupt_requests: list[AskRequest] | None = None
    ask_responses: list[AskResponse] | None = None


def run_context_agent_eval(
    *,
    intent: str = DEFAULT_CONTEXT_AGENT_EVAL_INTENT,
    state_file: str | Path | None = None,
    config_path: str | Path | None = None,
    dependencies: PlannerDependencies | None = None,
    sync_ask: bool = False,
) -> ContextAgentEvalResult:
    resolved_state_file = resolve_context_agent_eval_state_file(state_file)
    state = load_toml_state(resolved_state_file)
    request = PlannerRequest(instruction=intent, state=state)
    interrupt_requests: list[AskRequest] = []
    ask_responses: list[AskResponse] = []
    resolved_dependencies = dependencies or PlannerDependencies()
    if sync_ask:
        resolved_dependencies = _with_cli_ask_responder(
            resolved_dependencies,
            interrupt_requests=interrupt_requests,
            ask_responses=ask_responses,
        )
    planner = create_planner(
        state=state,
        dependencies=resolved_dependencies,
        config_path=str(config_path) if config_path is not None else None,
    )
    planner.load_skills_tool.invoke({"skill_ids": ["context_agent"]})
    payload = build_context_agent_payload(request)
    delegated = planner.delegate_tool.invoke({"target": "context_agent", "payload": payload})
    bundle = ContextBundle.model_validate((delegated.get("result") or {}))
    ask_interaction = "not_needed"
    ask_interaction_message = "No ask interaction was needed for this run."
    if sync_ask and interrupt_requests:
        ask_interaction = "resumed"
        ask_interaction_message = "CLI collected ask answers and resumed Context Agent execution in the same run."
    elif bundle.pending_interrupt is not None:
        ask_interaction = "pending"
        ask_interaction_message = "Context Agent is waiting for ask input before it can finish generating the bundle."
    return ContextAgentEvalResult(
        payload=payload,
        bundle=bundle,
        state_file=resolved_state_file,
        ask_interaction=ask_interaction,
        ask_interaction_message=ask_interaction_message,
        interrupt_requests=interrupt_requests or list(bundle.ask_requests),
        ask_responses=ask_responses or list(bundle.ask_responses),
    )


def resolve_context_agent_eval_state_file(path: str | Path | None = None) -> Path:
    return Path(path or DEFAULT_CONTEXT_AGENT_EVAL_STATE_FILE).expanduser().resolve()


def render_context_agent_eval(
    result: ContextAgentEvalResult,
    *,
    output_format: str = "human",
) -> str:
    if output_format == "json":
        payload = {
            "state_file": str(result.state_file),
            "payload": result.payload,
            "bundle": result.bundle.model_dump(),
            "ask_interaction": result.ask_interaction,
            "ask_interaction_message": result.ask_interaction_message,
            "interrupt_requests": [item.model_dump() for item in (result.interrupt_requests or [])],
            "ask_responses": [item.model_dump() for item in (result.ask_responses or [])],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return _render_human_context_agent_eval(result)


def _render_human_context_agent_eval(result: ContextAgentEvalResult) -> str:
    lines = [
        "Context Agent Eval",
        f"state_file: {result.state_file}",
        "",
        "Delegated Payload",
        f"- intent: {result.payload.get('intent', '')}",
        f"- goal: {result.payload.get('goal', '')}",
        _render_text_list("requests", list(result.payload.get("requests") or [])),
        "",
        "Realtime Bundle",
        f"- status: {result.bundle.status}",
        f"- instruction: {result.bundle.instruction}",
        f"- normalized_instruction: {result.bundle.normalized_instruction}",
        f"- action: {result.bundle.action or '<none>'}",
        f"- resolved_entities: {json.dumps(result.bundle.resolved_entities, ensure_ascii=False, sort_keys=True)}",
        f"- ask_interaction: {result.ask_interaction}",
        "",
        _render_evidence_section("rule_evidence", result.bundle.rule_evidence),
        "",
        _render_evidence_section("state_evidence", result.bundle.state_evidence),
        "",
        _render_citation_section(result.bundle.model_dump().get("citations", [])),
        "",
        _render_ask_section(result.interrupt_requests or result.bundle.ask_requests),
        "",
        _render_trace_section(list(result.bundle.notes)),
        "",
        _render_text_list("notes", list(result.bundle.notes)),
    ]
    if result.ask_interaction_message:
        lines.extend(["", f"ask_interaction_message: {result.ask_interaction_message}"])
    if result.ask_responses:
        lines.extend(["", _render_ask_response_section(result.ask_responses)])
    if result.ask_interaction == "pending":
        lines.extend(
            [
                "",
                "next_step: Provide ask input to resume Context Agent and generate the final bundle.",
            ]
        )
    elif result.ask_interaction == "resumed":
        lines.extend(
            [
                "",
                "resume_result: Context Agent resumed after ask and returned the final bundle in this CLI run.",
            ]
        )
    return "\n".join(lines).rstrip()


def _render_evidence_section(name: str, items: list[Any]) -> str:
    lines = [f"{name} ({len(items)})"]
    if not items:
        lines.append("- <none>")
        return "\n".join(lines)
    for item in items:
        summary = getattr(item, "summary", "")
        source = getattr(item, "source", None) or "<unknown>"
        locator = getattr(item, "locator", None) or "<none>"
        lines.append(f"- [{source}] {locator}: {summary}")
    return "\n".join(lines)


def _render_citation_section(items: list[dict[str, Any]]) -> str:
    lines = [f"citations ({len(items)})"]
    if not items:
        lines.append("- <none>")
        return "\n".join(lines)
    for item in items:
        lines.append(
            "- "
            + " | ".join(
                [
                    f"source={item.get('source') or '<none>'}",
                    f"locator={item.get('locator') or '<none>'}",
                    f"detail={item.get('detail') or '<none>'}",
                ]
            )
        )
    return "\n".join(lines)


def _render_text_list(name: str, items: list[str]) -> str:
    lines = [f"{name} ({len(items)})"]
    if not items:
        lines.append("- <none>")
        return "\n".join(lines)
    for item in items:
        lines.append(f"- {item}")
    return "\n".join(lines)


def _render_ask_section(items: list[Any]) -> str:
    lines = [f"ask_requests ({len(items)})"]
    if not items:
        lines.append("- <none>")
        return "\n".join(lines)
    for item in items:
        lines.append(f"- {item.prompt}")
        for option in getattr(item, "options", []):
            suffix = " (default)" if option.id == getattr(item, "default_option_id", None) else ""
            detail = f" | {option.description}" if option.description else ""
            lines.append(f"  - {option.id}: {option.label}{suffix}{detail}")
        if getattr(item, "allow_custom_input", False):
            lines.append("  - custom_input: allowed")
    return "\n".join(lines)


def _render_ask_response_section(items: list[AskResponse]) -> str:
    lines = [f"ask_responses ({len(items)})"]
    for item in items:
        answer = item.custom_input if item.custom_input is not None else item.selected_option_id or "<none>"
        lines.append(f"- {item.question_id}: {answer}")
    return "\n".join(lines)


def _render_trace_section(items: list[str]) -> str:
    trace_items = [item for item in items if item.startswith("trace:")]
    lines = [f"agent_trace ({len(trace_items)})"]
    if not trace_items:
        lines.append("- <none>")
        return "\n".join(lines)
    for item in trace_items:
        lines.append(f"- {item}")
    return "\n".join(lines)


def maybe_collect_cli_ask_responses(result: ContextAgentEvalResult) -> ContextAgentEvalResult:
    if not (result.interrupt_requests or result.bundle.ask_requests):
        result.ask_interaction = "not_needed"
        result.ask_interaction_message = "No ask interaction was needed for this run."
        return result
    responses = prompt_for_ask_requests(list(result.interrupt_requests or result.bundle.ask_requests))
    result.ask_responses = [item if isinstance(item, AskResponse) else AskResponse.model_validate(item) for item in responses]
    result.ask_interaction = "collected"
    result.ask_interaction_message = "Collected DM answers for all ask requests in the CLI eval."
    return result


def mark_cli_ask_interaction_skipped(
    result: ContextAgentEvalResult,
    *,
    reason: str,
) -> ContextAgentEvalResult:
    if not (result.interrupt_requests or result.bundle.ask_requests):
        result.ask_interaction = "not_needed"
        result.ask_interaction_message = "No ask interaction was needed for this run."
        return result
    result.ask_interaction = "skipped"
    result.ask_interaction_message = reason
    return result


def _with_cli_ask_responder(
    dependencies: PlannerDependencies,
    *,
    interrupt_requests: list[AskRequest],
    ask_responses: list[AskResponse],
) -> PlannerDependencies:
    def responder(request: AskRequest) -> AskResponse:
        interrupt_requests.append(request)
        response = prompt_for_ask_requests([request])[0]
        ask_responses.append(response)
        return response

    return PlannerDependencies(
        ask_tool=None,
        ask_responder=responder,
        grep_tool=dependencies.grep_tool,
        search_tool=dependencies.search_tool,
        lint_tool=dependencies.lint_tool,
        execute_tool=dependencies.execute_tool,
        context_agent=dependencies.context_agent,
        resolution_agent=dependencies.resolution_agent,
    )


__all__ = [
    "ContextAgentEvalResult",
    "DEFAULT_CONTEXT_AGENT_EVAL_INTENT",
    "DEFAULT_CONTEXT_AGENT_EVAL_STATE_FILE",
    "mark_cli_ask_interaction_skipped",
    "maybe_collect_cli_ask_responses",
    "render_context_agent_eval",
    "resolve_context_agent_eval_state_file",
    "run_context_agent_eval",
]
