from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from langchain.agents import create_agent

from augury.config import ProjectConfig
from augury.planner.model_loader import load_planner_chat_model
from augury.planner.prompt_loader import (
    PlannerNodePrompts,
    load_planner_node_prompts,
    render_prompt_template,
)
from augury.planner.task_document import TaskDocumentSchema, TaskDraft

DslAgentFactory = Callable[..., Any]


@dataclass(slots=True)
class DslNodeDependencies:
    template_tool: Any | None = None
    lint_tool: Any | None = None
    model: str | None = None
    max_tool_calls: int = 5
    system_prompt: str | None = None
    user_prompt_template: str | None = None
    project_config: ProjectConfig | None = None
    config_path: str | Path | None = None
    agent_factory: DslAgentFactory = create_agent


class DslNode:
    def __init__(self, dependencies: DslNodeDependencies | None = None) -> None:
        self.dependencies = dependencies or DslNodeDependencies()
        self._agent: Any | None = None

    @property
    def tools(self) -> list[Any]:
        return [
            tool
            for tool in [self.dependencies.template_tool, self.dependencies.lint_tool]
            if tool is not None
        ]

    def run(self, draft: TaskDraft) -> tuple[dict[str, Any], dict[str, Any] | None]:
        agent = self._get_agent()
        response = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": _build_dsl_user_message(
                            draft,
                            dependencies=self.dependencies,
                        ),
                    }
                ]
            },
            config={"recursion_limit": _recursion_limit_for_tool_budget(self.dependencies.max_tool_calls)},
        )
        document = _coerce_task_document(response)
        lint_results = _extract_lint_results(response)
        lint_calls_used = len(lint_results)
        latest_lint_result = lint_results[-1] if lint_results else None
        used_fallback = False
        if latest_lint_result is None and self.dependencies.lint_tool is not None:
            latest_lint_result = self.dependencies.lint_tool.invoke({"task_document": document})
            lint_calls_used += 1
            used_fallback = True
        decorated_lint_result = _decorate_lint_result(
            latest_lint_result,
            lint_calls_used=lint_calls_used,
            max_tool_calls=self.dependencies.max_tool_calls,
            used_fallback=used_fallback,
        )
        return document, decorated_lint_result

    def _get_agent(self) -> Any:
        if self._agent is None:
            prompt_set = _resolve_prompt_set(self.dependencies)
            self._agent = self.dependencies.agent_factory(
                model=_resolve_model(self.dependencies),
                tools=self.tools,
                system_prompt=prompt_set.system_prompt,
                response_format=TaskDocumentSchema,
                name="planner_dsl_node",
            )
        return self._agent


def _resolve_model(dependencies: DslNodeDependencies) -> str:
    return load_planner_chat_model(
        project_config=dependencies.project_config,
        config_path=dependencies.config_path,
        model_override=dependencies.model,
    )


def _build_dsl_user_message(
    draft: TaskDraft,
    *,
    dependencies: DslNodeDependencies | None = None,
) -> str:
    prompt_set = _resolve_prompt_set(dependencies or DslNodeDependencies())
    return render_prompt_template(
        prompt_set.user_prompt_template,
        {
            "task_draft_json": draft.model_dump_json(indent=2),
        },
    )


def _coerce_task_document(response: Any) -> dict[str, Any]:
    candidate = response
    if isinstance(response, dict) and "structured_response" in response:
        candidate = response["structured_response"]
    if isinstance(candidate, TaskDocumentSchema):
        return candidate.model_dump()
    if hasattr(candidate, "model_dump"):
        candidate = candidate.model_dump()
    validated = TaskDocumentSchema.model_validate(candidate)
    return validated.model_dump()


def _resolve_prompt_set(dependencies: DslNodeDependencies):
    if dependencies.system_prompt is not None and dependencies.user_prompt_template is not None:
        return PlannerNodePrompts(
            system_prompt=dependencies.system_prompt,
            user_prompt_template=dependencies.user_prompt_template,
        )
    loaded = load_planner_node_prompts(
        node_name="dsl_node",
        project_config=dependencies.project_config,
        config_path=dependencies.config_path,
    )
    if dependencies.system_prompt is not None:
        return PlannerNodePrompts(
            system_prompt=dependencies.system_prompt,
            user_prompt_template=loaded.user_prompt_template,
        )
    if dependencies.user_prompt_template is not None:
        return PlannerNodePrompts(
            system_prompt=loaded.system_prompt,
            user_prompt_template=dependencies.user_prompt_template,
        )
    return loaded


def _extract_lint_results(response: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for message in _iter_response_messages(response):
        if _get_message_name(message) != "lint":
            continue
        parsed = _parse_lint_message_content(_get_message_content(message))
        if parsed is not None:
            results.append(parsed)
    return results


def _iter_response_messages(response: Any) -> list[Any]:
    if isinstance(response, dict):
        messages = response.get("messages", [])
        return messages if isinstance(messages, list) else []
    messages = getattr(response, "messages", [])
    return messages if isinstance(messages, list) else []


def _get_message_name(message: Any) -> str | None:
    if isinstance(message, dict):
        name = message.get("name")
        return str(name) if name is not None else None
    name = getattr(message, "name", None)
    return str(name) if name is not None else None


def _get_message_content(message: Any) -> Any:
    if isinstance(message, dict):
        return message.get("content")
    return getattr(message, "content", None)


def _parse_lint_message_content(content: Any) -> dict[str, Any] | None:
    if isinstance(content, dict):
        return content if isinstance(content.get("status"), str) else None
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) and isinstance(parsed.get("status"), str) else None
    if isinstance(content, list):
        text_fragments: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                text_fragments.append(item["text"])
        if text_fragments:
            return _parse_lint_message_content("".join(text_fragments))
    return None


def _decorate_lint_result(
    lint_result: dict[str, Any] | None,
    *,
    lint_calls_used: int,
    max_tool_calls: int,
    used_fallback: bool,
) -> dict[str, Any] | None:
    if lint_result is None:
        return None
    decorated = dict(lint_result)
    decorated["dsl_node_meta"] = {
        "lint_calls": lint_calls_used,
        "max_tool_calls": max_tool_calls,
        "used_fallback": used_fallback,
    }
    return decorated


def _recursion_limit_for_tool_budget(max_tool_calls: int) -> int:
    bounded_calls = max(1, max_tool_calls)
    # Tool loops alternate between model and tool nodes; give the graph enough
    # headroom for the initial model turn plus the requested tool budget.
    return bounded_calls * 2 + 3
