from __future__ import annotations

from typing import Any, Literal, Protocol

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class RuntimeProtocol(Protocol):
    def list_skills(self) -> list[dict[str, Any]]: ...

    def load_skills(self, skill_ids: list[str]) -> dict[str, Any]: ...

    def delegate(self, target: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class SkillDescriptor(BaseModel):
    id: str
    kind: Literal["agent"]
    description: str
    tools: list[str] = Field(default_factory=list)
    loaded: bool = False


class ListSkillsResult(BaseModel):
    status: Literal["ok"]
    items: list[SkillDescriptor] = Field(default_factory=list)


class LoadSkillsInput(BaseModel):
    skill_ids: list[str] = Field(min_length=1)


class LoadSkillsResult(BaseModel):
    status: Literal["ok", "no_match"]
    loaded: list[SkillDescriptor] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class DelegateInput(BaseModel):
    target: str
    payload: dict[str, Any] = Field(default_factory=dict)


class DelegateResult(BaseModel):
    status: Literal["ok", "error"]
    target: str
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None


class ListSkillsTool(BaseTool):
    name: str = "list_skills"
    description: str = "列出主 agent 可加载和可委派的子 agent profile。"

    runtime: Any = Field(exclude=True)

    def _run(self) -> dict[str, Any]:
        return ListSkillsResult(status="ok", items=self.runtime.list_skills()).model_dump()


class LoadSkillsTool(BaseTool):
    name: str = "load_skills"
    description: str = "按 skill id 装配主 agent 可委派的子 agent profile。"
    args_schema: type[BaseModel] = LoadSkillsInput

    runtime: Any = Field(exclude=True)

    def _run(self, skill_ids: list[str]) -> dict[str, Any]:
        return self.runtime.load_skills(skill_ids)


class DelegateTool(BaseTool):
    name: str = "delegate"
    description: str = "把结构化 payload 委派给已装配的子 agent。"
    args_schema: type[BaseModel] = DelegateInput

    runtime: Any = Field(exclude=True)

    def _run(self, target: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.runtime.delegate(target, payload)


def create_list_skills_tool(runtime: RuntimeProtocol) -> ListSkillsTool:
    return ListSkillsTool(runtime=runtime)


def create_load_skills_tool(runtime: RuntimeProtocol) -> LoadSkillsTool:
    return LoadSkillsTool(runtime=runtime)


def create_delegate_tool(runtime: RuntimeProtocol) -> DelegateTool:
    return DelegateTool(runtime=runtime)
