from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError


DEFAULT_PROJECT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "config.toml"
PROJECT_LEVEL_CONFIG_SECTIONS = frozenset({"planner", "search"})
STATIC_FIXTURE_CATEGORIES = frozenset(
    {"demo_fixtures", "task_documents", "field_maps"}
)


class ProjectConfigError(ValueError):
    """Raised when the shared project configuration cannot be loaded."""


class PlannerConfig(BaseModel):
    model: str = Field(min_length=1)
    base_url: str | None = None
    api_key_env: str = Field(min_length=1)
    api_key: str | None = None
    timeout: float = Field(gt=0)
    max_retries: int = Field(ge=0)
    interrupt_on: dict[str, Any] = Field(default_factory=dict)
    max_planning_rounds: int = Field(ge=1)
    tool_budget: int = Field(ge=1)
    prompt: "PlannerPromptConfig"
    smoke: "PlannerSmokeConfig"


class PlannerPromptConfig(BaseModel):
    directory: str = Field(min_length=1)
    system_file: str = Field(min_length=1)
    user_file: str = Field(min_length=1)


class PlannerSmokeConfig(BaseModel):
    world_state_file: str = Field(min_length=1)


class SearchAPIConfig(BaseModel):
    api_key_env: str = Field(min_length=1)
    api_key: str | None = None
    base_url: str = Field(min_length=1)


class SearchModelsConfig(BaseModel):
    dense_embedding: str = Field(min_length=1)
    sparse_embedding: str = Field(min_length=1)
    reranker: str = Field(min_length=1)


class SearchQdrantConfig(BaseModel):
    url: str = Field(min_length=1)
    collection_name: str = Field(min_length=1)
    dense_vector_name: str = Field(min_length=1)
    sparse_vector_name: str = Field(min_length=1)


class SearchConfig(BaseModel):
    api: SearchAPIConfig
    models: SearchModelsConfig
    qdrant: SearchQdrantConfig
    default_limit: int = Field(ge=1, le=20)
    default_fetch_k: int = Field(ge=1)
    rerank_timeout: float = Field(gt=0)


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planner: PlannerConfig
    search: SearchConfig


_CONFIG_CACHE: dict[tuple[Path, bool], ProjectConfig] = {}


def load_project_config(
    config_path: str | Path | None = None,
    *,
    resolve_secrets: bool = True,
) -> ProjectConfig:
    resolved_path = resolve_project_config_path(config_path)
    cache_key = (resolved_path, resolve_secrets)
    cached = _CONFIG_CACHE.get(cache_key)
    if cached is not None:
        return cached

    try:
        raw_bytes = resolved_path.read_bytes()
    except FileNotFoundError as exc:
        raise ProjectConfigError(f"Project config file was not found: {resolved_path}") from exc
    except OSError as exc:
        raise ProjectConfigError(f"Failed to read project config file {resolved_path}: {exc}") from exc

    try:
        payload = tomllib.loads(raw_bytes.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ProjectConfigError(f"Project config file must be valid UTF-8: {resolved_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ProjectConfigError(f"Project config file is not valid TOML: {resolved_path}: {exc}") from exc

    try:
        config = ProjectConfig.model_validate(payload)
    except PydanticValidationError as exc:
        raise ProjectConfigError(
            f"Project config file failed validation: {resolved_path}: {exc}"
        ) from exc

    if resolve_secrets:
        config = _resolve_project_secrets(config)

    _CONFIG_CACHE[cache_key] = config
    return config


def resolve_project_config_path(config_path: str | Path | None = None) -> Path:
    return Path(config_path or DEFAULT_PROJECT_CONFIG_PATH).expanduser().resolve()


def resolve_path_from_config(
    path_value: str | Path,
    *,
    config_path: str | Path | None = None,
) -> Path:
    candidate = Path(path_value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (resolve_project_config_path(config_path).parent / candidate).resolve()


def clear_project_config_cache() -> None:
    _CONFIG_CACHE.clear()


def is_project_level_config_section(section: str) -> bool:
    return section in PROJECT_LEVEL_CONFIG_SECTIONS


def _resolve_project_secrets(config: ProjectConfig) -> ProjectConfig:
    planner_api_key = _read_required_env(
        config.planner.api_key_env,
        section="planner",
    )
    search_api_key = _read_required_env(
        config.search.api.api_key_env,
        section="search.api",
    )
    return config.model_copy(
        update={
            "planner": config.planner.model_copy(update={"api_key": planner_api_key}),
            "search": config.search.model_copy(
                update={
                    "api": config.search.api.model_copy(update={"api_key": search_api_key}),
                }
            ),
        }
    )


def _read_required_env(env_name: str, *, section: str) -> str:
    value = os.getenv(env_name)
    if value is None or not value.strip():
        raise ProjectConfigError(
            f"Project config requires environment variable {env_name!r} for section {section}"
        )
    return value


__all__ = [
    "DEFAULT_PROJECT_CONFIG_PATH",
    "PROJECT_LEVEL_CONFIG_SECTIONS",
    "PlannerConfig",
    "PlannerPromptConfig",
    "PlannerSmokeConfig",
    "ProjectConfig",
    "ProjectConfigError",
    "SearchConfig",
    "STATIC_FIXTURE_CATEGORIES",
    "clear_project_config_cache",
    "is_project_level_config_section",
    "load_project_config",
    "resolve_path_from_config",
    "resolve_project_config_path",
]
