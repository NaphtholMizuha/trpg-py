from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_openai import ChatOpenAI

from augury.config import ProjectConfig, ProjectConfigError, load_project_config


def load_planner_chat_model(
    *,
    project_config: ProjectConfig | None = None,
    config_path: str | Path | None = None,
    model_override: str | None = None,
) -> Any:
    if project_config is None:
        try:
            project_config = load_project_config(
                config_path=config_path,
                resolve_secrets=True,
            )
        except ProjectConfigError:
            if model_override is not None:
                return model_override
            return "openai:gpt-4.1-mini"

    planner_config = project_config.planner
    model_name = model_override or planner_config.model
    if planner_config.api_key:
        return ChatOpenAI(
            model=model_name,
            api_key=planner_config.api_key,
            base_url=planner_config.base_url,
            timeout=planner_config.timeout,
            max_retries=planner_config.max_retries,
        )
    return model_name
