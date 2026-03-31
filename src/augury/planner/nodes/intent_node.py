from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from langchain.agents import create_agent

from augury.config import ProjectConfig, ProjectConfigError, load_project_config
from augury.planner.task_document import TaskBrief, normalize_instruction

IntentAgentFactory = Callable[..., Any]

DEFAULT_INTENT_SYSTEM_PROMPT = """
You are the intent stage of a TRPG planner.
Turn the DM instruction into a TaskBrief.
Use tools when they help gather state context.
Return only the structured TaskBrief response.
""".strip()


@dataclass(slots=True)
class IntentNodeDependencies:
    grep_tool: Any | None = None
    read_tool: Any | None = None
    search_tool: Any | None = None
    model: str | None = None
    system_prompt: str = DEFAULT_INTENT_SYSTEM_PROMPT
    project_config: ProjectConfig | None = None
    agent_factory: IntentAgentFactory = create_agent


class IntentNode:
    def __init__(self, dependencies: IntentNodeDependencies | None = None) -> None:
        self.dependencies = dependencies or IntentNodeDependencies()
        self._agent: Any | None = None

    @property
    def tools(self) -> list[Any]:
        tools = [
            self.dependencies.grep_tool,
            self.dependencies.read_tool,
            self.dependencies.search_tool,
        ]
        return [tool for tool in tools if tool is not None]

    def run(self, instruction: str) -> TaskBrief:
        agent = self._get_agent()
        response = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": _build_intent_user_message(instruction),
                    }
                ]
            }
        )
        brief = _coerce_task_brief(response)
        if not brief.normalized_instruction:
            brief = brief.model_copy(update={"normalized_instruction": normalize_instruction(instruction)})
        if not brief.instruction:
            brief = brief.model_copy(update={"instruction": instruction})
        if not brief.summary:
            brief = brief.model_copy(update={"summary": brief.normalized_instruction or instruction})
        if not brief.write_targets:
            brief = brief.model_copy(update={"write_targets": ["planner.debug.last_instruction"]})
        return brief

    def _get_agent(self) -> Any:
        if self._agent is None:
            self._agent = self.dependencies.agent_factory(
                model=_resolve_model(self.dependencies),
                tools=self.tools,
                system_prompt=self.dependencies.system_prompt,
                response_format=TaskBrief,
                name="planner_intent_node",
            )
        return self._agent


def _resolve_model(dependencies: IntentNodeDependencies) -> str:
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


def _build_intent_user_message(instruction: str) -> str:
    payload = {
        "instruction": instruction,
        "requirements": [
            "Normalize the instruction.",
            "Produce a concise summary.",
            "Collect relevant context through tools when helpful.",
            "Return explicit write_targets and defaults when uncertain.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _coerce_task_brief(response: Any) -> TaskBrief:
    candidate = response
    if isinstance(response, dict) and "structured_response" in response:
        candidate = response["structured_response"]
    if isinstance(candidate, TaskBrief):
        return candidate
    if hasattr(candidate, "model_dump"):
        candidate = candidate.model_dump()
    return TaskBrief.model_validate(candidate)
