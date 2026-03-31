from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from augury.config import (
    DEFAULT_PROJECT_CONFIG_PATH,
    ProjectConfig,
    load_project_config,
    resolve_path_from_config,
)


@dataclass(frozen=True, slots=True)
class PlannerNodePrompts:
    system_prompt: str
    user_prompt_template: str


def load_planner_node_prompts(
    *,
    node_name: str,
    project_config: ProjectConfig | None = None,
    config_path: str | Path | None = None,
) -> PlannerNodePrompts:
    resolved_config_path = config_path or DEFAULT_PROJECT_CONFIG_PATH
    config = project_config or load_project_config(
        config_path=resolved_config_path,
        resolve_secrets=False,
    )
    prompt_dir = resolve_path_from_config(
        config.planner.prompt.directory,
        config_path=resolved_config_path,
    )
    node_prompt_config = _resolve_node_prompt_config(config, node_name=node_name)
    system_path = (prompt_dir / node_prompt_config.system_file).resolve()
    user_path = (prompt_dir / node_prompt_config.user_file).resolve()
    return PlannerNodePrompts(
        system_prompt=system_path.read_text(encoding="utf-8").strip(),
        user_prompt_template=user_path.read_text(encoding="utf-8").strip(),
    )


def render_prompt_template(template: str, values: dict[str, Any]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", _stringify_prompt_value(value))
    return rendered


def _resolve_node_prompt_config(
    config: ProjectConfig,
    *,
    node_name: str,
):
    if node_name == "task_node":
        return config.planner.task_node_prompt
    if node_name == "dsl_node":
        return config.planner.dsl_node_prompt
    raise ValueError(f"Unsupported planner node prompt namespace: {node_name!r}")


def _stringify_prompt_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if hasattr(value, "model_dump_json"):
        return value.model_dump_json(indent=2)
    return str(value)
