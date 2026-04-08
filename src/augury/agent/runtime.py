from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from augury.agent.models import AskRequest, AskResponse, ContextBundle, ErrorInfo, PlannerRequest, PlannerResult, ResolutionBundle
from augury.agent.subagents.context_agent import ContextAgent, ContextAgentDependencies
from augury.agent.subagents.resolution_agent import ResolutionAgent, ResolutionAgentDependencies
from augury.agent.tools.ask import AskTool, create_ask_tool
from augury.agent.tools.execute import ExecuteTool, create_execute_tool
from augury.agent.tools.orchestration import (
    SkillDescriptor,
    create_delegate_tool,
    create_list_skills_tool,
    create_load_skills_tool,
)
from augury.agent.tools.search_stub import create_search_stub_tool
from augury.planner.tools import create_grep_tool, create_lint_tool, create_search_tool


@dataclass(slots=True)
class PlannerDependencies:
    ask_tool: AskTool | None = None
    ask_responder: Callable[[AskRequest], AskResponse | dict[str, Any]] | None = None
    grep_tool: Any | None = None
    search_tool: Any | None = None
    lint_tool: Any | None = None
    execute_tool: ExecuteTool | None = None
    context_agent: ContextAgent | None = None
    resolution_agent: ResolutionAgent | None = None


@dataclass(slots=True)
class _SkillRegistration:
    descriptor: SkillDescriptor
    factory: Callable[[], Any]


class AgentSkillRegistry:
    def __init__(self) -> None:
        self._registrations: dict[str, _SkillRegistration] = {}
        self._loaded: dict[str, Any] = {}

    def register_agent(self, *, skill_id: str, description: str, tools: list[str], factory: Callable[[], Any]) -> None:
        self._registrations[skill_id] = _SkillRegistration(
            descriptor=SkillDescriptor(id=skill_id, kind="agent", description=description, tools=list(tools)),
            factory=factory,
        )

    def list_skills(self) -> list[dict[str, Any]]:
        return [
            registration.descriptor.model_copy(update={"loaded": skill_id in self._loaded}).model_dump()
            for skill_id, registration in sorted(self._registrations.items())
        ]

    def load_skills(self, skill_ids: list[str]) -> dict[str, Any]:
        loaded: list[dict[str, Any]] = []
        missing: list[str] = []
        for skill_id in skill_ids:
            registration = self._registrations.get(skill_id)
            if registration is None:
                missing.append(skill_id)
                continue
            if skill_id not in self._loaded:
                self._loaded[skill_id] = registration.factory()
            loaded.append(
                registration.descriptor.model_copy(update={"loaded": True}).model_dump()
            )
        return {
            "status": "ok" if loaded else "no_match",
            "loaded": loaded,
            "missing": missing,
        }

    def delegate(self, target: str, payload: dict[str, Any]) -> dict[str, Any]:
        if target not in self._loaded:
            return {
                "status": "error",
                "target": target,
                "error": {"type": "missing_skill", "message": f"Skill {target!r} has not been loaded"},
            }
        result = self._loaded[target].run(payload)
        payload_dict = result.model_dump() if hasattr(result, "model_dump") else dict(result)
        return {"status": "ok", "target": target, "result": payload_dict}

    @property
    def loaded_skill_ids(self) -> list[str]:
        return sorted(self._loaded)


class PlannerAgent:
    def __init__(
        self,
        *,
        state: dict[str, Any] | None = None,
        dependencies: PlannerDependencies | None = None,
        config_path: str | None = None,
        roller: Any | None = None,
    ) -> None:
        self.state = state or {}
        self.config_path = config_path
        self.dependencies = dependencies or PlannerDependencies()

        self.grep_tool = self.dependencies.grep_tool or create_grep_tool(state_provider=self._state_provider)
        self.search_tool = self.dependencies.search_tool or _build_safe_search_tool(config_path=config_path)
        self.lint_tool = self.dependencies.lint_tool or create_lint_tool()
        self.ask_tool = self.dependencies.ask_tool or create_ask_tool(responder=self.dependencies.ask_responder)
        self.execute_tool = self.dependencies.execute_tool or create_execute_tool(
            state_provider=self._state_provider,
            roller=roller,
        )

        self.context_agent = self.dependencies.context_agent or ContextAgent(
            ContextAgentDependencies(
                grep_tool=self.grep_tool,
                search_tool=self.search_tool,
                ask_tool=self.ask_tool,
                state_provider=self._state_provider,
            )
        )
        self.resolution_agent = self.dependencies.resolution_agent or ResolutionAgent(
            ResolutionAgentDependencies(
                lint_tool=self.lint_tool,
                execute_tool=self.execute_tool,
            )
        )

        self.registry = AgentSkillRegistry()
        self.registry.register_agent(
            skill_id="context_agent",
            description="Collects rule and state evidence with grep/search and can issue ask requests.",
            tools=["grep", "search", "ask"],
            factory=lambda: self.context_agent,
        )
        self.registry.register_agent(
            skill_id="resolution_agent",
            description="Builds, lints, and executes candidate task documents.",
            tools=["lint", "execute"],
            factory=lambda: self.resolution_agent,
        )

        self.list_skills_tool = create_list_skills_tool(self.registry)
        self.load_skills_tool = create_load_skills_tool(self.registry)
        self.delegate_tool = create_delegate_tool(self.registry)

    def invoke(self, request: str | PlannerRequest) -> PlannerResult:
        planner_request = request if isinstance(request, PlannerRequest) else PlannerRequest(instruction=request)
        if planner_request.state:
            self.state = planner_request.state

        self.list_skills_tool.invoke({})
        load_result = self.load_skills_tool.invoke({"skill_ids": ["context_agent", "resolution_agent"]})
        loaded_skills = [item["id"] for item in load_result.get("loaded", [])]
        context_payload = build_context_agent_payload(planner_request)

        context_response = self.delegate_tool.invoke(
            {
                "target": "context_agent",
                "payload": context_payload,
            }
        )
        if context_response.get("status") != "ok":
            error = context_response.get("error") or {}
            return PlannerResult(
                status="error",
                instruction=planner_request.instruction,
                loaded_skills=loaded_skills,
                error=ErrorInfo(type=error.get("type", "delegate_error"), message=error.get("message", "")),
            )

        context_bundle = ContextBundle.model_validate(context_response["result"])
        if context_bundle.status == "blocked":
            return PlannerResult(
                status="blocked",
                instruction=planner_request.instruction,
                loaded_skills=loaded_skills,
                context_bundle=context_bundle,
                ask_requests=list(context_bundle.ask_requests),
                ask_responses=list(context_bundle.ask_responses),
                pending_interrupt=context_bundle.pending_interrupt,
                missing_info=[item.prompt for item in context_bundle.ask_requests],
                blocked_reasons=list(context_bundle.notes),
            )
        if context_bundle.ask_requests and planner_request.task_document is None:
            return PlannerResult(
                status="needs_human",
                instruction=planner_request.instruction,
                loaded_skills=loaded_skills,
                context_bundle=context_bundle,
                ask_requests=list(context_bundle.ask_requests),
                ask_responses=list(context_bundle.ask_responses),
                pending_interrupt=context_bundle.pending_interrupt,
                missing_info=[item.prompt for item in context_bundle.ask_requests],
            )

        resolution_response = self.delegate_tool.invoke(
            {
                "target": "resolution_agent",
                "payload": {
                    "instruction": planner_request.instruction,
                    "state": self.state,
                    "context_bundle": context_bundle.model_dump(),
                    "task_document": planner_request.task_document,
                },
            }
        )
        if resolution_response.get("status") != "ok":
            error = resolution_response.get("error") or {}
            return PlannerResult(
                status="error",
                instruction=planner_request.instruction,
                loaded_skills=loaded_skills,
                context_bundle=context_bundle,
                error=ErrorInfo(type=error.get("type", "delegate_error"), message=error.get("message", "")),
            )

        resolution_bundle = ResolutionBundle.model_validate(resolution_response["result"])
        if resolution_bundle.status == "blocked":
            planner_status = "needs_human" if resolution_bundle.task_document is None else "blocked"
            return PlannerResult(
                status=planner_status,
                instruction=planner_request.instruction,
                loaded_skills=loaded_skills,
                context_bundle=context_bundle,
                resolution_bundle=resolution_bundle,
                task_document=resolution_bundle.task_document,
                lint_result=resolution_bundle.lint_result,
                execution_report=resolution_bundle.execution_report,
                state_changes=list(resolution_bundle.state_changes),
                ask_requests=list(context_bundle.ask_requests),
                ask_responses=list(context_bundle.ask_responses),
                pending_interrupt=context_bundle.pending_interrupt,
                missing_info=[item.prompt for item in context_bundle.ask_requests],
                blocked_reasons=list(resolution_bundle.blocked_reasons),
            )

        return PlannerResult(
            status="ready",
            instruction=planner_request.instruction,
            loaded_skills=loaded_skills,
            context_bundle=context_bundle,
            resolution_bundle=resolution_bundle,
            task_document=resolution_bundle.task_document,
            lint_result=resolution_bundle.lint_result,
            execution_report=resolution_bundle.execution_report,
            state_changes=list(resolution_bundle.state_changes),
            ask_requests=list(context_bundle.ask_requests),
            ask_responses=list(context_bundle.ask_responses),
            pending_interrupt=context_bundle.pending_interrupt,
        )

    def _state_provider(self) -> dict[str, Any]:
        return self.state


def create_planner(
    *,
    state: dict[str, Any] | None = None,
    dependencies: PlannerDependencies | None = None,
    config_path: str | None = None,
    roller: Any | None = None,
) -> PlannerAgent:
    return PlannerAgent(
        state=state,
        dependencies=dependencies,
        config_path=config_path,
        roller=roller,
    )


def build_context_agent_payload(
    request: str | PlannerRequest,
) -> dict[str, Any]:
    planner_request = request if isinstance(request, PlannerRequest) else PlannerRequest(instruction=request)
    return {
        "intent": planner_request.instruction,
        "goal": _build_context_goal(planner_request.instruction),
        "requests": _build_context_requests(planner_request.instruction),
        "ask_responses": [item.model_dump() for item in planner_request.ask_responses],
    }


def _build_safe_search_tool(*, config_path: str | None) -> Any:
    try:
        return create_search_tool(config_path=config_path)
    except Exception as exc:
        return create_search_stub_tool(reason=f"{exc.__class__.__name__}: {exc}")


def _build_context_goal(instruction: str) -> str:
    action = instruction.strip() or "当前用户意图"
    return f"为后续 resolution 收集与“{action}”直接相关的规则证据、状态证据和缺口。"


def _build_context_requests(instruction: str) -> list[str]:
    requests = [
        "识别这条意图中的执行者对应哪个实体；如果不能唯一定位，明确指出歧义或缺失。",
    ]
    normalized = instruction.strip()
    if "攻击" in normalized:
        requests.append(
            "识别这条意图中的目标对应哪个实体；如果匹配多个候选，列出候选并说明为什么仍不唯一。"
        )
    if any(token in normalized for token in ("火球术", "闪电束", "火焰箭", "治疗伤口")):
        requests.append("检索与该法术结算直接相关的规则证据，优先保留能支持后续 resolution 的关键条文。")
    elif any(token in normalized for token in ("长剑", "弯刀", "短弓")):
        requests.append("检索与该武器攻击结算直接相关的规则证据，优先保留命中与伤害判定所需条文。")
    else:
        requests.append("检索与这条意图对应动作最直接相关的规则证据，避免返回泛化摘要。")
    if "火球术" in normalized and "位置" not in normalized:
        requests.append("确认当前是否缺少爆点或目标位置这类会阻塞范围法术结算的前置事实。")
    if "记录" in normalized and "AC" in normalized.upper():
        requests.append("确认记录状态前需要读取哪些当前状态事实，并说明是否已经能从现有状态中定位。")
    return requests
