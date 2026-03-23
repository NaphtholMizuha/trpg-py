"""
DeepPlannerAgent - 深度规划 Agent

输出单步任务。
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from ..config import PLANNER_SYSTEM_PROMPT
from ..types import (
    TaskExecution,
)
from ..utils.logging import get_logger
from ..skills import detect_intent_with_keywords, get_registry, Skill
from .base import BaseAgent

logger = get_logger(__name__)

_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"
TASK_TEMPLATE = (_PROMPT_DIR / "planner_task.md").read_text(encoding="utf-8")
FORCE_OUTPUT_PROMPT = (_PROMPT_DIR / "force_output" / "planner.txt").read_text(encoding="utf-8")


class DeepPlannerAgent(BaseAgent):
    """支持多 skill 的规划 Agent。"""

    _COMMON_FIELD_HINTS = (
        "临时HP",
        "HP",
        "临时AC加值",
        "AC",
        "反应",
        "附赠动作",
        "护盾术状态",
        "状态",
        "位置",
        "速度",
        "先攻调整值",
    )

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
        tools: list[BaseTool] | None = None,
        skills: list[Skill] | None = None,
    ):
        super().__init__(model, api_key, base_url, tools, max_iterations=4)
        self.skills = skills or []
        self._logger = get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    def get_system_prompt(self, mode: str = "plan", skills: list[Skill] | None = None) -> str:
        base_prompt = PLANNER_SYSTEM_PROMPT

        selected_skills = skills if skills is not None else self.skills

        if not selected_skills:
            return base_prompt

        skills_content = "\n\n" + "=" * 50 + "\n\n".join(
            [f"## Skill: {s.name}\n{s.content}" for s in selected_skills]
        )
        return f"{base_prompt}\n\n## 可用的 Skills\n{skills_content}"

    def plan(self, user_input: str) -> TaskExecution:
        self._logger.info("DeepPlannerAgent 分析指令", user_input=user_input)
        intent_type, selected_skill = detect_intent_with_keywords(user_input)
        selected_skills = [selected_skill] if selected_skill is not None else self.skills

        messages = [
            SystemMessage(content=self.get_system_prompt(mode="plan", skills=selected_skills)),
            HumanMessage(content=TASK_TEMPLATE.format(user_input=user_input)),
        ]
        try:
            task = self._invoke_agent(
                messages=messages,
                response_format=TaskExecution,
                force_output_prompt=FORCE_OUTPUT_PROMPT,
            )
            return self._normalize_task(self._ensure_task_id(task))
        except Exception as exc:
            self._logger.exception(f"Planner structured output 失败，已回退: {exc}")
            return self._build_fallback_task(user_input, intent_type=intent_type)

    def _ensure_task_id(self, task: TaskExecution) -> TaskExecution:
        if not task.task_id:
            task.task_id = f"task_{uuid.uuid4().hex[:8]}"
        return task

    def _normalize_task(self, task: TaskExecution) -> TaskExecution:
        kv_roots = self._extract_kv_roots(task.context)

        if task.actor and self._contains_cjk(task.actor):
            inferred = self._infer_root_from_text(task.actor, kv_roots, task.context)
            if inferred:
                task.actor = inferred

        if task.target and self._contains_cjk(task.target):
            inferred = self._infer_root_from_text(task.target, kv_roots, task.context)
            if inferred:
                task.target = inferred

        task.write_targets = self._normalize_write_targets(task)
        return task

    def _normalize_write_targets(self, task: TaskExecution) -> list[str]:
        context_keys = self._extract_context_keys(task.context)
        context_key_set = set(context_keys)
        normalized_targets: list[str] = []
        seen: set[str] = set()

        for target in task.write_targets or []:
            path = (target or "").strip()
            if not path:
                continue

            if self._is_field_level_path(path):
                self._append_unique(normalized_targets, seen, path)
                continue

            if path not in context_key_set:
                continue

            inferred_fields = self._infer_fields_for_root(task, path)
            for field in inferred_fields:
                self._append_unique(normalized_targets, seen, f"{path}.{field}")

        self._augment_resource_write_targets(task, context_key_set, normalized_targets, seen)
        return normalized_targets

    def _augment_resource_write_targets(
        self,
        task: TaskExecution,
        context_key_set: set[str],
        normalized_targets: list[str],
        seen: set[str],
    ) -> None:
        actor = (task.actor or "").strip()
        if not actor:
            return

        spell_slot_root = f"{actor}.spell_slots"
        if spell_slot_root not in context_key_set:
            return

        if any(target.startswith(f"{spell_slot_root}.") for target in normalized_targets):
            return

        if not self._task_likely_consumes_spell_slots(task):
            return

        for field in self._infer_spell_slot_fields(task, spell_slot_root):
            self._append_unique(normalized_targets, seen, f"{spell_slot_root}.{field}")

    def _task_likely_consumes_spell_slots(self, task: TaskExecution) -> bool:
        text = "\n".join(
            blob
            for blob in (
                task.description,
                task.context,
                *task.execution_steps,
                *task.raw_query_appendix,
            )
            if blob
        )
        keywords = (
            "施放",
            "施法",
            "法术",
            "法术位",
            "spell",
            "cast",
        )
        return (
            (task.action_type or "").lower() == "spell"
            or any(keyword in text for keyword in keywords)
        )

    def _infer_spell_slot_fields(self, task: TaskExecution, root_key: str) -> list[str]:
        available_fields = [
            field
            for field in self._extract_kv_fields(task.context, root_key)
            if re.fullmatch(r"\d+环", field)
        ]
        if not available_fields:
            return []

        focused_text = "\n".join(
            blob
            for blob in (
                task.description,
                *task.execution_steps,
                *task.raw_query_appendix,
            )
            if blob
        )
        mentioned = self._extract_ordered_mentions(focused_text, available_fields)
        if mentioned:
            return mentioned[:1]
        return available_fields[:1]

    def _infer_fields_for_root(self, task: TaskExecution, root_key: str) -> list[str]:
        available_fields = self._extract_kv_fields(task.context, root_key)
        if not available_fields:
            return []

        ordered_blobs = [
            task.description,
            task.context,
            *task.execution_steps,
            *task.raw_query_appendix,
        ]

        if root_key.endswith(".spell_slots"):
            levels = self._extract_ordered_mentions(
                "\n".join(blob for blob in ordered_blobs if blob),
                [field for field in available_fields if re.fullmatch(r"\d+环", field)],
            )
            if levels:
                return levels

        referenced_fields = self._extract_fields_near_root(root_key, ordered_blobs, available_fields)
        if referenced_fields:
            return referenced_fields

        mentioned_fields = self._extract_ordered_mentions(
            "\n".join(blob for blob in ordered_blobs if blob),
            available_fields,
        )
        if mentioned_fields:
            return mentioned_fields

        return available_fields[:1]

    def _extract_context_keys(self, text: str) -> list[str]:
        if not text:
            return []
        seen: set[str] = set()
        ordered: list[str] = []
        matches = re.findall(r"\[KV\s+([A-Za-z][A-Za-z0-9_.]*)\]", text)
        matches.extend(re.findall(r"\[KV\]\s*([A-Za-z][A-Za-z0-9_.]*)\s*:", text))
        for key in matches:
            if key not in seen:
                seen.add(key)
                ordered.append(key)
        return ordered

    def _extract_kv_fields(self, context: str, root_key: str) -> list[str]:
        if not context or not root_key:
            return []

        match = re.search(rf"\[KV {re.escape(root_key)}\]\s*([^\n]+)", context)
        if not match:
            match = re.search(rf"\[KV\]\s*{re.escape(root_key)}\s*:\s*([^\n]+)", context)
        if not match:
            return []

        fields: list[str] = []
        seen: set[str] = set()
        for chunk in match.group(1).split("|"):
            part = chunk.strip()
            if ":" not in part:
                continue
            field_name = part.split(":", 1)[0].strip()
            if not field_name or field_name in seen:
                continue
            seen.add(field_name)
            fields.append(field_name)
        return fields

    def _extract_fields_near_root(
        self,
        root_key: str,
        blobs: list[str],
        available_fields: list[str],
    ) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        escaped_root = re.escape(root_key)
        patterns = (
            rf"\[KV {escaped_root}\]\s*([^\n]+)",
            rf"更新\[{escaped_root}\]\s*([^\n。；]*)",
            rf"更新{escaped_root}\s*([^\n。；]*)",
        )

        for blob in blobs:
            if not blob:
                continue
            for pattern in patterns:
                for match in re.finditer(pattern, blob):
                    nearby_text = match.group(1)
                    for field in self._extract_ordered_mentions(nearby_text, available_fields):
                        if field in seen:
                            continue
                        seen.add(field)
                        ordered.append(field)
        return ordered

    def _extract_ordered_mentions(self, text: str, candidates: list[str]) -> list[str]:
        if not text:
            return []

        matches: list[tuple[int, str]] = []
        seen: set[str] = set()

        for candidate in candidates:
            idx = text.find(candidate)
            if idx == -1 or candidate in seen:
                continue
            seen.add(candidate)
            matches.append((idx, candidate))

        for candidate in self._COMMON_FIELD_HINTS:
            if candidate in seen or candidate not in candidates:
                continue
            idx = text.find(candidate)
            if idx == -1:
                continue
            seen.add(candidate)
            matches.append((idx, candidate))

        matches.sort(key=lambda item: item[0])
        return [candidate for _, candidate in matches]

    def _is_field_level_path(self, path: str) -> bool:
        return len(path.split(".")) >= 3

    def _append_unique(self, items: list[str], seen: set[str], value: str) -> None:
        if value and value not in seen:
            seen.add(value)
            items.append(value)

    def _extract_kv_roots(self, text: str) -> list[str]:
        if not text:
            return []
        roots = re.findall(r"\[KV\s+([A-Za-z][A-Za-z0-9_]*)\.[^\]]+\]", text)
        roots.extend(re.findall(r"\[KV\]\s*([A-Za-z][A-Za-z0-9_]*)\.[A-Za-z0-9_.]+\s*:", text))
        seen: set[str] = set()
        ordered: list[str] = []
        for root in roots:
            if root not in seen:
                seen.add(root)
                ordered.append(root)
        return ordered

    def _infer_root_from_text(self, display_name: str, kv_roots: list[str], context: str) -> str | None:
        for root in kv_roots:
            if f"[KV {root}.status]" in context:
                status_match = re.search(rf"\[KV {re.escape(root)}\.status\]\s*([^\n]+)", context)
                if status_match:
                    status_text = status_match.group(1)
                    primary_name = status_text.split("|", 1)[0].strip()
                    if primary_name and (primary_name.startswith(display_name) or display_name.startswith(primary_name)):
                        return root
        return None

    def _contains_cjk(self, text: str) -> bool:
        return bool(re.search(r"[\u4e00-\u9fff]", text))

    def _build_fallback_task(self, original_input: str, intent_type: str = "standard") -> TaskExecution:
        return TaskExecution(
            task_id=f"task_{uuid.uuid4().hex[:8]}",
            description=original_input,
            context=f"[Needs Confirmation] 未能从 Planner 输出中解析到结构化任务，使用原始指令作为最小上下文。\n\n原始指令: {original_input}",
            actor="DM" if intent_type == "world_edit" else "未知",
            target=None,
            source="dm",
            task_category="world_edit" if intent_type == "world_edit" else "normal",
        )

def create_deep_planner_agent(
    model: str,
    api_key: str | None,
    base_url: str | None,
    tools: list[BaseTool],
    skill_names: list[str] | None = None,
) -> DeepPlannerAgent:
    registry = get_registry()
    if skill_names is None:
        skills = list(registry.get_all_skills().values())
    else:
        skills = []
        for name in skill_names:
            skill = registry.get_skill(name)
            if skill:
                skills.append(skill)

    return DeepPlannerAgent(
        model=model,
        api_key=api_key,
        base_url=base_url,
        tools=tools,
        skills=skills,
    )
