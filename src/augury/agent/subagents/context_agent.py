from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from augury.agent.models import AskRequest, AskResponse, Citation, ContextBundle, ErrorInfo, EvidenceItem, PendingInterrupt
from augury.agent.tools.ask import AskInterrupt


@dataclass(slots=True)
class ContextAgentDependencies:
    grep_tool: Any
    search_tool: Any
    ask_tool: Any
    state_provider: Callable[[], dict[str, Any]] | None = None


class ContextAgent:
    def __init__(self, dependencies: ContextAgentDependencies) -> None:
        self.dependencies = dependencies

    def run(self, payload: dict[str, Any]) -> ContextBundle:
        intent = str(payload.get("intent", ""))
        goal = _normalize_text(payload.get("goal", ""))
        requests = _normalize_requests(payload.get("requests"))
        state = self._resolve_state()
        normalized_intent = _normalize_text(intent)
        responses = _normalize_ask_responses(payload.get("ask_responses"))
        response_map = {item.question_id: item for item in responses}

        try:
            analysis, consumed_responses = self._resolve_analysis_with_ask(normalized_intent, state, response_map)
            state_evidence = self._collect_state_evidence(state, analysis)
            rule_evidence, citations, search_error = self._collect_rule_evidence(analysis)
        except AskInterrupt as interrupt:
            pending_request = interrupt.request
            analysis = _analyze_intent(normalized_intent, state, overrides=_build_analysis_overrides(response_map))
            notes = list(analysis["notes"])
            if goal:
                notes.append(f"goal={goal}")
            if requests:
                notes.append(f"requests={len(requests)}")
            return ContextBundle(
                status="needs_human",
                instruction=intent,
                normalized_instruction=normalized_intent,
                action=analysis["action"],
                resolved_entities=analysis["resolved_entities"],
                derived_context=analysis["derived_context"],
                ask_requests=[pending_request],
                ask_responses=responses,
                pending_interrupt=PendingInterrupt(tool_name="ask", request=pending_request),
                notes=notes,
            )
        except Exception as exc:  # pragma: no cover - defensive safety net
            return ContextBundle(
                status="error",
                instruction=intent,
                normalized_instruction=normalized_intent,
                action=None,
                resolved_entities={},
                error=ErrorInfo(type=exc.__class__.__name__, message=str(exc)),
            )

        internal_gaps = list(analysis["internal_gaps"])
        notes = list(analysis["notes"]) + list(internal_gaps)
        if goal:
            notes.append(f"goal={goal}")
        if requests:
            notes.append(f"requests={len(requests)}")
        if consumed_responses:
            notes.append(f"ask_responses={len(consumed_responses)}")
        if search_error is not None:
            notes.append(f"search_error: {search_error}")

        status = "ready"
        if search_error is not None:
            status = "blocked"
        elif internal_gaps:
            status = "blocked"

        return ContextBundle(
            status=status,
            instruction=intent,
            normalized_instruction=normalized_intent,
            action=analysis["action"],
            resolved_entities=analysis["resolved_entities"],
            derived_context=analysis["derived_context"],
            rule_evidence=rule_evidence,
            state_evidence=state_evidence,
            citations=citations,
            ask_requests=[],
            ask_responses=consumed_responses,
            notes=notes,
        )

    def _resolve_state(self) -> dict[str, Any]:
        if self.dependencies.state_provider is not None:
            return self.dependencies.state_provider() or {}
        return {}

    def _resolve_analysis_with_ask(
        self,
        intent: str,
        state: dict[str, Any],
        response_map: dict[str, AskResponse],
    ) -> tuple[dict[str, Any], list[AskResponse]]:
        overrides = _build_analysis_overrides(response_map)
        consumed: list[AskResponse] = list(response_map.values())

        while True:
            analysis = _analyze_intent(intent, state, overrides=overrides)
            next_request = _next_clarification_request(analysis, response_map)
            if next_request is not None:
                response = self._invoke_ask(next_request, response_map)
                if response not in consumed:
                    response_map[response.question_id] = response
                    consumed.append(response)
                    overrides = _build_analysis_overrides(response_map)
                    continue

            return analysis, consumed

    def _invoke_ask(
        self,
        request: dict[str, Any],
        response_map: dict[str, AskResponse],
    ) -> AskResponse:
        question_id = str(request["question_id"])
        response = response_map.get(question_id)
        payload = self.dependencies.ask_tool.invoke(
            {
                "question_id": question_id,
                "prompt": request["prompt"],
                "options": request.get("options") or [],
                "default_option_id": request.get("default_option_id"),
                "allow_custom_input": bool(request.get("allow_custom_input", False)),
                "custom_input_label": request.get("custom_input_label"),
                "custom_input_placeholder": request.get("custom_input_placeholder"),
                "reason": request.get("reason"),
                "resume_response": response.model_dump() if response is not None else None,
            }
        )
        return AskResponse.model_validate(payload)

    def _collect_state_evidence(
        self,
        state: dict[str, Any],
        analysis: dict[str, Any],
    ) -> list[EvidenceItem]:
        expressions = _build_grep_expressions(analysis)
        if not expressions:
            return []
        result = self.dependencies.grep_tool.invoke({"expressions": expressions, "limit": 8})
        if result.get("status") == "error":
            raise RuntimeError(result["error"]["message"])
        evidence: list[EvidenceItem] = []
        for match in result.get("matches", []):
            evidence.append(
                EvidenceItem(
                    kind="state",
                    summary=f"{match['key']} = {match['value']}",
                    source="grep",
                    locator=match["key"],
                    data={"sim": match.get("sim")},
                )
            )
        return evidence

    def _collect_rule_evidence(
        self,
        analysis: dict[str, Any],
    ) -> tuple[list[EvidenceItem], list[Citation], str | None]:
        query = _build_rule_query(analysis)
        if query is None:
            return [], [], None
        result = self.dependencies.search_tool.invoke({"query": query, "mode": "balanced", "limit": 3})
        if result.get("status") == "error":
            error = result.get("error", {})
            return [], [], f"{error.get('type', 'error')}: {error.get('message', '')}"
        evidence: list[EvidenceItem] = []
        citations: list[Citation] = []
        for hit in result.get("hits", []):
            metadata = hit.get("metadata", {}) if isinstance(hit.get("metadata"), dict) else {}
            title = metadata.get("title") or metadata.get("path") or "<rule>"
            evidence.append(
                EvidenceItem(
                    kind="rule",
                    summary=f"{title}: {hit.get('text', '')}",
                    source="search",
                    locator=str(metadata.get("path") or metadata.get("title") or ""),
                    data={"score": hit.get("score"), "metadata": metadata},
                )
            )
            citations.append(
                Citation(
                    source=str(title),
                    locator=str(metadata.get("path") or metadata.get("book") or ""),
                    detail=str(metadata.get("doc_type") or ""),
                )
            )
        return evidence, citations, None


def _analyze_intent(intent: str, state: dict[str, Any], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    overrides = overrides or {}
    entities = _collect_entities(state)
    matches = _find_entity_matches(intent, entities)
    action = _identify_action(intent)
    resolved_entities: dict[str, str] = {}
    notes: list[str] = []
    internal_gaps: list[str] = []
    target_matches: list[dict[str, str]] = []

    actor_id = overrides.get("actor_id") or (matches[0]["id"] if matches else None)
    if actor_id is not None:
        resolved_entities["actor_id"] = actor_id
    else:
        notes.append("actor_missing")

    target_fragment = _extract_target_fragment(intent, action)
    target_matches = _match_target_fragment(target_fragment, entities)

    target_id = None
    target_override = overrides.get("target_id")
    if target_override is not None:
        target_id = target_override
    elif target_fragment == "self" and actor_id is not None:
        target_id = actor_id
    elif len(matches) >= 2:
        target_id = matches[1]["id"]
    elif len(target_matches) == 1:
        target_id = target_matches[0]["id"]
    elif len(target_matches) > 1:
        notes.append(f"target_ambiguous={','.join(item['id'] for item in target_matches)}")

    if target_id is not None:
        resolved_entities["target_id"] = target_id
    elif action in {"weapon_attack", "spell_attack", "heal_spell", "area_spell"} and target_fragment not in {None, "self"}:
        notes.append("target_resolution_needed")

    point_value = overrides.get("area_point")
    missing_point = (
        action == "area_spell"
        and "火球术" in intent
        and "所在位置" not in intent
        and "位置" not in intent
        and point_value is None
    )
    if missing_point:
        notes.append("area_point_needed")
    elif point_value is not None:
        notes.append(f"area_point={point_value}")
    if action == "record_state" and actor_id is None:
        internal_gaps.append("记录状态前需要先识别被记录的实体。")

    if action is None:
        internal_gaps.append("当前最小求解器还不认识这条指令对应的动作类型。")
    else:
        notes.append(f"action={action}")
    clarification_requests = _build_clarification_requests(
        actor_missing=actor_id is None,
        target_fragment=target_fragment,
        target_matches=target_matches,
        target_resolution_needed=target_id is None and action in {"weapon_attack", "spell_attack", "heal_spell", "area_spell"} and target_fragment not in {None, "self"},
        missing_point=missing_point,
    )
    return {
        "action": action,
        "actor_missing": actor_id is None,
        "clarification_requests": clarification_requests,
        "derived_context": {"area_point": point_value} if point_value is not None else {},
        "internal_gaps": internal_gaps,
        "resolved_entities": resolved_entities,
        "notes": notes,
        "target_fragment": target_fragment,
        "target_matches": target_matches,
        "target_resolution_needed": target_id is None and action in {"weapon_attack", "spell_attack", "heal_spell", "area_spell"} and target_fragment not in {None, "self"},
        "missing_point": missing_point,
        "area_point": point_value,
    }


def _collect_entities(state: dict[str, Any]) -> list[dict[str, str]]:
    pool = state.get("actors") if isinstance(state, dict) else None
    if not isinstance(pool, dict):
        return []
    entities: list[dict[str, str]] = []
    for entity_id, payload in pool.items():
        if not isinstance(payload, dict):
            continue
        aliases = {str(entity_id).casefold()}
        name = payload.get("name")
        if isinstance(name, str):
            aliases.add(name.casefold())
        entities.append({"id": str(entity_id), "aliases": "\n".join(sorted(aliases))})
    return entities


def _find_entity_matches(instruction: str, entities: list[dict[str, str]]) -> list[dict[str, Any]]:
    lowered = instruction.casefold()
    matches: list[dict[str, Any]] = []
    for entity in entities:
        positions = [lowered.find(alias) for alias in entity["aliases"].splitlines() if alias and lowered.find(alias) >= 0]
        if not positions:
            continue
        matches.append({"id": entity["id"], "position": min(positions)})
    matches.sort(key=lambda item: item["position"])
    return matches


def _identify_action(instruction: str) -> str | None:
    if "火球术" in instruction or "闪电束" in instruction:
        return "area_spell"
    if "治疗伤口" in instruction:
        return "heal_spell"
    if "火焰箭" in instruction:
        return "spell_attack"
    if any(token in instruction for token in ("长剑", "弯刀", "短弓")):
        return "weapon_attack"
    if "记录" in instruction and "AC" in instruction.upper():
        return "record_state"
    return None


def _build_clarification_requests(
    *,
    actor_missing: bool,
    target_fragment: str | None,
    target_matches: list[dict[str, str]],
    target_resolution_needed: bool,
    missing_point: bool,
) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    if actor_missing:
        requests.append(
            {
                "question_id": "actor_identification",
                "prompt": "请确认这条意图中的执行者实体。",
                "options": [],
                "default_option_id": None,
                "allow_custom_input": True,
                "custom_input_label": "请输入执行者实体 ID",
                "custom_input_placeholder": "例如 aldera",
                "reason": "Context Agent 需要确认由谁来执行这条意图，再决定后续取证与结算。",
            }
        )
    if len(target_matches) > 1:
        requests.append(
            {
                "question_id": "target_disambiguation",
                "prompt": "请选择这次意图中的目标实体。",
                "options": [
                    {
                        "id": item["id"],
                        "label": item["id"],
                        "description": "由 Context Agent 根据当前世界状态匹配出的候选实体。",
                    }
                    for item in target_matches
                ],
                "default_option_id": target_matches[0]["id"],
                "allow_custom_input": True,
                "custom_input_label": "如果都不是，请输入正确的目标实体 ID",
                "custom_input_placeholder": "例如 goblin_3",
                "reason": "当前目标描述对应多个候选，Context Agent 需要 DM 决定真正目标。",
            }
        )
    elif target_resolution_needed and target_fragment not in {None, "self"}:
        requests.append(
            {
                "question_id": "target_identification",
                "prompt": "请确认这条意图中的目标实体。",
                "options": [],
                "default_option_id": None,
                "allow_custom_input": True,
                "custom_input_label": "请输入目标实体 ID",
                "custom_input_placeholder": f"例如 {target_fragment}",
                "reason": "Context Agent 还不能把目标描述安全落到唯一实体。",
            }
        )
    if missing_point:
        requests.append(
            {
                "question_id": "area_point",
                "prompt": "请确认范围法术的爆点或目标位置。",
                "options": [
                    {
                        "id": "use_target_position",
                        "label": "以已提及目标的位置为爆点",
                        "description": "如果 DM 只是省略了位置，可以按目标当前位置处理。",
                    },
                ],
                "default_option_id": "use_target_position" if target_fragment else None,
                "allow_custom_input": True,
                "custom_input_label": "请输入爆点或位置描述",
                "custom_input_placeholder": "例如 (5, 10) 或 goblin_1所在位置",
                "reason": "范围法术仍缺少足够的爆点或位置信息。",
            }
        )
    return requests


def _next_clarification_request(
    analysis: dict[str, Any],
    response_map: dict[str, AskResponse],
) -> dict[str, Any] | None:
    for request in analysis.get("clarification_requests") or []:
        question_id = str(request.get("question_id") or "")
        if question_id and question_id not in response_map:
            return request
    return None


def _normalize_text(value: str) -> str:
    collapsed = re.sub(r"\s+", " ", value or "")
    return collapsed.strip()


def _normalize_requests(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_normalize_text(item) for item in value if _normalize_text(str(item))]


def _normalize_ask_responses(value: Any) -> list[AskResponse]:
    if not isinstance(value, list):
        return []
    normalized: list[AskResponse] = []
    for item in value:
        try:
            normalized.append(AskResponse.model_validate(item))
        except Exception:
            continue
    return normalized


def _build_analysis_overrides(response_map: dict[str, AskResponse]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    actor = response_map.get("actor_identification")
    if actor is not None:
        overrides["actor_id"] = actor.custom_input or actor.selected_option_id
    target = response_map.get("target_disambiguation") or response_map.get("target_identification")
    if target is not None:
        overrides["target_id"] = target.custom_input or target.selected_option_id
    area_point = response_map.get("area_point")
    if area_point is not None:
        overrides["area_point"] = area_point.custom_input or area_point.selected_option_id
    return overrides


def _extract_target_fragment(instruction: str, action: str | None) -> str | None:
    if "对自己" in instruction or "自己施放" in instruction:
        return "self"
    if action in {"weapon_attack", "spell_attack", "area_spell"} and "攻击" in instruction:
        fragment = instruction.split("攻击", maxsplit=1)[1]
        return fragment.replace("所在位置", "").strip() or None
    if action == "heal_spell" and "对" in instruction:
        fragment = instruction.split("对", maxsplit=1)[1]
        return fragment.split("施放", maxsplit=1)[0].strip() or None
    return None


def _match_target_fragment(fragment: str | None, entities: list[dict[str, str]]) -> list[dict[str, str]]:
    if fragment in {None, "", "self"}:
        return []
    lowered = fragment.casefold()
    matches = []
    for entity in entities:
        aliases = entity["aliases"].splitlines()
        if any(lowered == alias or lowered in alias for alias in aliases):
            matches.append(entity)
    return matches


def _build_grep_expressions(analysis: dict[str, Any]) -> list[str]:
    expressions: list[str] = []
    actor_id = analysis["resolved_entities"].get("actor_id")
    target_id = analysis["resolved_entities"].get("target_id")
    action = analysis["action"]
    if actor_id:
        expressions.append(f"{actor_id} && position")
    if target_id:
        expressions.append(f"{target_id} && hp")
        expressions.append(f"{target_id} && dex && save")
    if action == "weapon_attack" and actor_id:
        expressions.append(f"{actor_id} && attack_bonus")
    if action in {"spell_attack", "area_spell"} and actor_id:
        expressions.append(f"{actor_id} && spell")
        expressions.append(f"{actor_id} && slot")
    if action == "record_state" and actor_id:
        expressions.append(f"{actor_id} && armor")
    return expressions


def _build_rule_query(analysis: dict[str, Any]) -> str | None:
    action = analysis["action"]
    if action == "weapon_attack":
        return "近战或远程武器攻击 攻击检定 伤害"
    if action == "spell_attack":
        return "火焰箭 法术攻击 火焰伤害"
    if action == "heal_spell":
        return "治疗伤口 恢复生命 消耗法术位"
    if action == "area_spell":
        target_id = analysis["resolved_entities"].get("target_id")
        if target_id and "orc" in target_id:
            return "闪电束 敏捷豁免 闪电伤害 半伤"
        return "火球术 敏捷豁免 火焰伤害 半伤"
    if action == "record_state":
        return "护甲等级 AC 状态记录"
    return None
