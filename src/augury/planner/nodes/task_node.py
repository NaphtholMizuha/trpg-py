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
                        "content": _build_task_user_message(
                            instruction,
                            dependencies=self.dependencies,
                        ),
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
        draft = draft.model_copy(
            update={
                "evidence": _filter_evidence(draft.evidence),
                "states": _filter_states(draft.states, draft=draft),
            }
        )
        draft = _ensure_area_effect_gaps(draft)
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


def _build_task_user_message(
    instruction: str,
    *,
    dependencies: TaskNodeDependencies | None = None,
) -> str:
    prompt_set = _resolve_prompt_set(dependencies or TaskNodeDependencies())
    return render_prompt_template(
        prompt_set.user_prompt_template,
        {
            "instruction": instruction,
        },
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


def _filter_evidence(lines: list[str]) -> list[str]:
    if not lines:
        return []

    filtered: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if not isinstance(line, str):
            continue
        normalized = line.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        filtered.append(normalized)
    return filtered


def _filter_states(lines: list[str], *, draft: TaskDraft) -> list[str]:
    if not lines:
        return []

    relevant_paths = {
        path.strip()
        for path in [*draft.reads, *draft.writes]
        if isinstance(path, str) and path.strip()
    }
    if not relevant_paths:
        return lines

    filtered: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if not isinstance(line, str):
            continue
        normalized_line = line.strip()
        if not normalized_line:
            continue
        path, _, _ = normalized_line.partition(" = ")
        normalized_path = path.strip()
        if not normalized_path:
            continue
        if _path_is_relevant(normalized_path, relevant_paths) and normalized_line not in seen:
            seen.add(normalized_line)
            filtered.append(normalized_line)
    return filtered


def _path_is_relevant(path: str, relevant_paths: set[str]) -> bool:
    if path in relevant_paths:
        return True
    return any(path.startswith(f"{candidate}.") for candidate in relevant_paths)


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


def _ensure_area_effect_gaps(draft: TaskDraft) -> TaskDraft:
    instruction_text = " ".join(
        part
        for part in [draft.instruction, draft.normalized_instruction, draft.task, *draft.judgments, *draft.evidence]
        if isinstance(part, str) and part.strip()
    ).lower()
    if not _looks_like_area_effect(instruction_text):
        return draft

    missing_info = list(draft.missing_info)
    reads = [item for item in draft.reads if isinstance(item, str)]
    states = [item for item in draft.states if isinstance(item, str)]

    has_position_support = any(".position" in item for item in [*reads, *states])
    has_range_gap = any(_mentions_range_gap(item) for item in missing_info)
    if not has_position_support and not has_range_gap:
        missing_info.append("缺少位置、爆点或覆盖范围证据，无法安全确认范围效果影响到哪些对象。")

    task_mentions_coverage = any(_mentions_coverage(item) for item in [draft.task, *draft.judgments, *draft.missing_info])
    if task_mentions_coverage:
        return draft.model_copy(update={"missing_info": missing_info})

    task = draft.task.strip()
    if task:
        task = (
            f"{task} 在执行伤害或豁免结算前，先确认覆盖范围、爆点与受影响对象集合。"
        )
    judgments = [
        "先根据位置、施法距离与覆盖范围确认哪些对象实际受到该范围效果影响。",
        *draft.judgments,
    ]
    return draft.model_copy(
        update={
            "task": task,
            "judgments": _filter_evidence(judgments),
            "missing_info": missing_info,
        }
    )


def _looks_like_area_effect(text: str) -> bool:
    keywords = (
        "范围",
        "半径",
        "爆炸",
        "burst",
        "cone",
        "line",
        "lightning bolt",
        "thunderwave",
        "fireball",
        "闪电束",
        "雷鸣波",
        "火球术",
    )
    return any(keyword in text for keyword in keywords)


def _mentions_range_gap(text: str) -> bool:
    normalized = (text or "").lower()
    keywords = ("位置", "爆点", "覆盖", "范围", "distance", "position", "area")
    return any(keyword in normalized for keyword in keywords)


def _mentions_coverage(text: str) -> bool:
    normalized = (text or "").lower()
    keywords = ("覆盖", "范围", "爆点", "受影响对象", "affected", "position", "distance")
    return any(keyword in normalized for keyword in keywords)
