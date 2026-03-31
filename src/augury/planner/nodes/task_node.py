from __future__ import annotations

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
from augury.planner.task_document import TaskDraft, normalize_instruction

TaskAgentFactory = Callable[..., Any]


@dataclass(slots=True)
class TaskNodeDependencies:
    grep_tool: Any | None = None
    read_tool: Any | None = None
    search_tool: Any | None = None
    model: str | None = None
    system_prompt: str | None = None
    user_prompt_template: str | None = None
    project_config: ProjectConfig | None = None
    config_path: str | Path | None = None
    agent_factory: TaskAgentFactory = create_agent


class TaskNode:
    def __init__(self, dependencies: TaskNodeDependencies | None = None) -> None:
        self.dependencies = dependencies or TaskNodeDependencies()
        self._agent: Any | None = None

    @property
    def tools(self) -> list[Any]:
        tools = [
            self.dependencies.grep_tool,
            self.dependencies.search_tool,
        ]
        return [tool for tool in tools if tool is not None]

    def run(self, instruction: str) -> TaskDraft:
        agent = self._get_agent()
        response = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": _build_task_user_message(instruction, self.dependencies),
                    }
                ]
            }
        )
        draft = _coerce_task_draft(response)
        normalized_instruction = normalize_instruction(instruction)
        if not draft.normalized_instruction:
            draft = draft.model_copy(update={"normalized_instruction": normalized_instruction})
        if not draft.instruction:
            draft = draft.model_copy(update={"instruction": instruction})
        if not draft.task:
            draft = draft.model_copy(
                update={"task": normalized_instruction or "Draft a planner task from the instruction."}
            )
        return draft

    def _get_agent(self) -> Any:
        if self._agent is None:
            prompt_set = _resolve_prompt_set(self.dependencies)
            self._agent = self.dependencies.agent_factory(
                model=_resolve_model(self.dependencies),
                tools=self.tools,
                system_prompt=prompt_set.system_prompt,
                response_format=TaskDraft,
                name="planner_task_node",
            )
        return self._agent


def _resolve_model(dependencies: TaskNodeDependencies) -> str:
    return load_planner_chat_model(
        project_config=dependencies.project_config,
        config_path=dependencies.config_path,
        model_override=dependencies.model,
    )


def _build_task_user_message(instruction: str, dependencies: TaskNodeDependencies | None = None) -> str:
    prompt_set = _resolve_prompt_set(dependencies or TaskNodeDependencies())
    return render_prompt_template(
        prompt_set.user_prompt_template,
        {"instruction": instruction},
    )


def _coerce_task_draft(response: Any) -> TaskDraft:
    candidate = response
    if isinstance(response, dict) and "structured_response" in response:
        candidate = response["structured_response"]
    if isinstance(candidate, TaskDraft):
        return candidate
    if hasattr(candidate, "model_dump"):
        candidate = candidate.model_dump()
    return TaskDraft.model_validate(candidate)


def _resolve_prompt_set(dependencies: TaskNodeDependencies):
    if dependencies.system_prompt is not None and dependencies.user_prompt_template is not None:
        return PlannerNodePrompts(
            system_prompt=dependencies.system_prompt,
            user_prompt_template=dependencies.user_prompt_template,
        )
    loaded = load_planner_node_prompts(
        node_name="task_node",
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
