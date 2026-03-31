from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from langchain.agents import create_agent

from augury.config import ProjectConfig, ProjectConfigError, load_project_config
from augury.planner.task_document import TaskBrief, TaskDocumentSchema

DslAgentFactory = Callable[..., Any]

DEFAULT_DSL_SYSTEM_PROMPT = """
You are the DSL stage of a TRPG planner.
Translate the TaskBrief into a valid TaskDocument.
Use only the provided tools that are relevant to DSL generation and validation.
Return only the structured TaskDocument response.
""".strip()


@dataclass(slots=True)
class DslNodeDependencies:
    lint_tool: Any | None = None
    model: str | None = None
    system_prompt: str = DEFAULT_DSL_SYSTEM_PROMPT
    project_config: ProjectConfig | None = None
    agent_factory: DslAgentFactory = create_agent


class DslNode:
    def __init__(self, dependencies: DslNodeDependencies | None = None) -> None:
        self.dependencies = dependencies or DslNodeDependencies()
        self._agent: Any | None = None

    @property
    def tools(self) -> list[Any]:
        return [tool for tool in [self.dependencies.lint_tool] if tool is not None]

    def run(self, brief: TaskBrief) -> tuple[dict[str, Any], dict[str, Any] | None]:
        agent = self._get_agent()
        response = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": _build_dsl_user_message(brief),
                    }
                ]
            }
        )
        document = _coerce_task_document(response)
        lint_result = None
        if self.dependencies.lint_tool is not None:
            lint_result = self.dependencies.lint_tool.invoke({"task_document": document})
        return document, lint_result

    def _get_agent(self) -> Any:
        if self._agent is None:
            self._agent = self.dependencies.agent_factory(
                model=_resolve_model(self.dependencies),
                tools=self.tools,
                system_prompt=self.dependencies.system_prompt,
                response_format=TaskDocumentSchema,
                name="planner_dsl_node",
            )
        return self._agent


def _resolve_model(dependencies: DslNodeDependencies) -> str:
    if dependencies.model:
        return dependencies.model
    config = dependencies.project_config
    if config is None:
        try:
            config = load_project_config(resolve_secrets=False)
        except ProjectConfigError:
            config = None
    if config is not None:
        return config.planner.model
    return "openai:gpt-4.1-mini"


def _build_dsl_user_message(brief: TaskBrief) -> str:
    return json.dumps(
        {
            "task_brief": brief.model_dump(),
            "requirements": [
                "Build a valid TaskDocument.",
                "Use the TaskBrief as the source of truth.",
                "Preserve write_targets when constructing state/resource steps.",
            ],
        },
        ensure_ascii=False,
        indent=2,
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
