from __future__ import annotations

from typing import Any

from augury.agent.orchestrate import PlannerDependencies
from augury.agent.tools.search_stub import create_search_stub_tool


DEFAULT_CONTEXT_AGENT_TEST_SYSTEM_PROMPT = "Test context agent system prompt"
DEFAULT_CONTEXT_AGENT_TEST_USER_PROMPT = """Intent: {{intent}}
Goal: {{goal}}
Requests:
{{requests_block}}

Existing ask responses:
{{ask_responses_json}}

Current state evidence:
{{state_evidence_json}}

Current rule evidence:
{{rule_evidence_json}}

Current tool trace:
{{trace_block}}
"""


class ScriptedContextAgentGraph:
    def __init__(self, tools: list[Any]) -> None:
        self.tools = {tool.name: tool for tool in tools}

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = _extract_user_prompt(payload)
        if "长剑攻击goblin_1" in prompt:
            self.tools["search"].invoke(
                {
                    "query": "近战或远程武器攻击 攻击检定 伤害",
                    "mode": "balanced",
                    "limit": 3,
                }
            )
            self.tools["grep"].invoke(
                {
                    "expressions": ["aldera && attack_bonus", "goblin_1 && hp"],
                    "limit": 8,
                }
            )
            return {
                "structured_response": {
                    "status": "ready",
                    "action": "weapon_attack",
                    "resolved_entities": {"actor_id": "aldera", "target_id": "goblin_1"},
                    "derived_context": {},
                    "notes": ["action=weapon_attack"],
                }
            }

        if "火球术攻击goblin_1" in prompt:
            self.tools["search"].invoke(
                {
                    "query": "火球术 敏捷豁免 火焰伤害 半伤",
                    "mode": "balanced",
                    "limit": 3,
                }
            )
            self.tools["grep"].invoke(
                {
                    "expressions": ["aldera && spell", "aldera && slot", "goblin_1 && hp"],
                    "limit": 8,
                }
            )
            return {
                "structured_response": {
                    "status": "ready",
                    "action": "area_spell",
                    "resolved_entities": {"actor_id": "aldera", "target_id": "goblin_1"},
                    "derived_context": {},
                    "notes": ["action=area_spell"],
                }
            }

        if "火球术攻击goblin" in prompt:
            self.tools["search"].invoke(
                {
                    "query": "火球术 敏捷豁免 火焰伤害 半伤",
                    "mode": "balanced",
                    "limit": 3,
                }
            )
            target_response = self.tools["ask"].invoke(
                {
                    "question_id": "target_disambiguation",
                    "prompt": "请选择这次意图中的目标实体。",
                    "options": [
                        {"id": "goblin_1", "label": "goblin_1"},
                        {"id": "goblin_2", "label": "goblin_2"},
                    ],
                    "default_option_id": "goblin_1",
                    "allow_custom_input": True,
                    "custom_input_label": "输入正确目标实体 ID",
                }
            )
            target_id = target_response.get("custom_input") or target_response.get("selected_option_id") or "goblin_1"
            point_response = self.tools["ask"].invoke(
                {
                    "question_id": "area_point",
                    "prompt": "请确认范围法术的爆点或目标位置。",
                    "options": [
                        {
                            "id": "use_target_position",
                            "label": "以已提及目标的位置为爆点",
                        }
                    ],
                    "default_option_id": "use_target_position",
                    "allow_custom_input": True,
                    "custom_input_label": "请输入爆点或位置描述",
                }
            )
            area_point = point_response.get("custom_input") or point_response.get("selected_option_id") or "use_target_position"
            self.tools["grep"].invoke(
                {
                    "expressions": [f"{target_id} && hp", "aldera && slot"],
                    "limit": 8,
                }
            )
            return {
                "structured_response": {
                    "status": "ready",
                    "action": "area_spell",
                    "resolved_entities": {"actor_id": "aldera", "target_id": target_id},
                    "derived_context": {"area_point": area_point},
                    "notes": ["action=area_spell"],
                }
            }

        if "记录Aldera当前AC供下一轮使用" in prompt:
            self.tools["grep"].invoke(
                {
                    "expressions": ["aldera && armor"],
                    "limit": 8,
                }
            )
            return {
                "structured_response": {
                    "status": "ready",
                    "action": "record_state",
                    "resolved_entities": {"actor_id": "aldera"},
                    "derived_context": {},
                    "notes": ["action=record_state"],
                }
            }

        return {
            "structured_response": {
                "status": "ready",
                "action": None,
                "resolved_entities": {},
                "derived_context": {},
                "notes": ["default_test_ready"],
            }
        }


def build_scripted_context_agent_dependencies(
    *,
    search_tool: Any | None = None,
    ask_responder: Any | None = None,
    system_prompt: str | None = None,
    user_prompt: str | None = None,
    agent_factory: Any | None = None,
    model: Any | None = None,
) -> PlannerDependencies:
    return PlannerDependencies(
        ask_responder=ask_responder,
        search_tool=search_tool or create_search_stub_tool(),
        context_agent_model=object() if model is None else model,
        context_agent_system_prompt=system_prompt or DEFAULT_CONTEXT_AGENT_TEST_SYSTEM_PROMPT,
        context_agent_user_prompt=user_prompt or DEFAULT_CONTEXT_AGENT_TEST_USER_PROMPT,
        context_agent_agent_factory=agent_factory or create_scripted_context_agent_agent,
    )


def create_scripted_context_agent_agent(**kwargs: Any) -> ScriptedContextAgentGraph:
    return ScriptedContextAgentGraph(list(kwargs.get("tools") or []))


def _extract_user_prompt(payload: dict[str, Any]) -> str:
    messages = payload.get("messages") if isinstance(payload, dict) else None
    if not isinstance(messages, list):
        return ""
    for item in reversed(messages):
        if isinstance(item, dict) and item.get("role") == "user":
            return str(item.get("content") or "")
    return ""
