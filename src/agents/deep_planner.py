"""
DeepPlannerAgent - 深度规划 Agent

输出单步任务。
"""
from __future__ import annotations

import re
import uuid

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from ..prompting import load_prompt
from ..types import (
    TaskExecution,
)
from ..utils.logging import get_logger
from ..skills import detect_intent_with_keywords, get_registry, Skill
from ..utils.kv_patch import KVPatch
from .base import BaseAgent

logger = get_logger(__name__)

PLANNER_SYSTEM_PROMPT = load_prompt("planner.md")
TASK_TEMPLATE = load_prompt("planner_task.md")
PLANNER_FORCE_OUTPUT_PROMPT = """请立即停止继续调用工具，直接输出最终的 TaskExecution JSON。

强制要求：
- 不要再调用任何工具
- 不要输出 TOOL_CALL / tool_call / minimax:tool_call / XML / Markdown 代码块
- 只返回一个可被 TaskExecution 解析的 JSON 对象
- 如果信息仍不完整，也必须直接收口，并把未决点写成 `[Needs Confirmation] [Default: ...]`
- 对同一争议点已经做过检索后，不要换措辞重复 search，直接收口
"""


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
        super().__init__(model, api_key, base_url, tools, max_iterations=10)
        self.skills = skills or []
        self._logger = get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    def get_system_prompt(self, mode: str = "plan", skills: list[Skill] | None = None) -> str:
        base_prompt = PLANNER_SYSTEM_PROMPT

        selected_skills = skills if skills is not None else self.skills

        if not selected_skills:
            return base_prompt

        return f"{base_prompt}\n\n{self._render_domain_modules(selected_skills)}"

    def _render_domain_modules(self, skills: list[Skill]) -> str:
        sections = [
            "## 领域 Skills",
            "下面这些内容只提供领域差异。",
            "不要重复它们与核心 planner 合同无关的通用 schema 规则。",
        ]
        for skill in skills:
            sections.extend(
                [
                    "",
                    f"## Domain Skill: {skill.name}",
                    skill.content.strip(),
                ]
            )
        return "\n".join(sections).strip()

    def plan(self, user_input: str) -> list[TaskExecution]:
        self._logger.info("DeepPlannerAgent 分析指令", user_input=user_input)
        search_tool = self.tools.get("search")
        if search_tool is not None and hasattr(search_tool, "reset_session"):
            search_tool.reset_session()
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
                force_output_prompt=PLANNER_FORCE_OUTPUT_PROMPT,
            )
            return [self._normalize_task(self._ensure_task_id(task))]
        except Exception as exc:
            self._logger.exception(f"Planner structured output 失败，已回退: {exc}")
            return [self._build_fallback_task(user_input, intent_type=intent_type)]

    def _ensure_task_id(self, task: TaskExecution) -> TaskExecution:
        if not task.task_id:
            task.task_id = f"task_{uuid.uuid4().hex[:8]}"
        return task

    def _normalize_task(self, task: TaskExecution) -> TaskExecution:
        task.context = self._hydrate_context_kv_lines(task.context)
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

    def _hydrate_context_kv_lines(self, context: str) -> str:
        if not context:
            return context

        kv_keys = self._extract_context_keys(context)
        if not kv_keys:
            return context

        snapshot = self._load_kv_snapshot(kv_keys)
        if not snapshot:
            return context

        hydrated_lines: list[str] = []
        for raw_line in context.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            hydrated_lines.append(self._hydrate_context_line(line, snapshot))
        return "\n".join(hydrated_lines).strip()

    def _load_kv_snapshot(self, keys: list[str]) -> dict[str, str]:
        tools = getattr(self, "tools", {}) or {}
        read_tool = tools.get("read")
        if read_tool is None:
            return {}

        store = getattr(read_tool, "store", None)
        if store is None:
            return {}

        get_multi = getattr(store, "get_multi", None)
        if callable(get_multi):
            return {
                key: value
                for key, value in get_multi(keys).items()
                if isinstance(value, str) and value
            }

        get_single = getattr(store, "get", None)
        if not callable(get_single):
            return {}

        snapshot: dict[str, str] = {}
        for key in keys:
            value = get_single(key)
            if isinstance(value, str) and value:
                snapshot[key] = value
        return snapshot

    def _hydrate_context_line(self, line: str, snapshot: dict[str, str]) -> str:
        match = re.match(
            r"^(?P<prefix>.*?\[KV\s+(?P<key>[A-Za-z][A-Za-z0-9_.]*)\])(?:\s+.*)?$",
            line,
        )
        if match is None:
            return line

        key = match.group("key")
        value = snapshot.get(key)
        if not value:
            return line
        return f"{match.group('prefix')} {value}"

    def _normalize_write_targets(self, task: TaskExecution) -> list[str]:
        context_keys = self._extract_context_keys(task.context)
        context_key_set = set(context_keys)
        allowed_additions = self._extract_allowed_additions(task.context)
        normalized_targets: list[str] = []
        seen: set[str] = set()

        for target in task.write_targets or []:
            path = (target or "").strip()
            if not path:
                continue

            if self._is_field_level_path(path):
                root_key = self._extract_root_key(path)
                if root_key not in context_key_set:
                    continue
                if self._extract_old_field_value_from_context(task.context, path) is None and path not in allowed_additions:
                    continue
                self._append_unique(normalized_targets, seen, path)
                continue

            if path not in context_key_set:
                continue

            inferred_fields = self._infer_fields_for_root(task, path)
            for field in inferred_fields:
                self._append_unique(normalized_targets, seen, f"{path}.{field}")

        return normalized_targets

    def _extract_allowed_additions(self, context: str) -> set[str]:
        allowed: set[str] = set()
        if not context:
            return allowed

        for raw_line in context.splitlines():
            line = raw_line.strip()
            if not line.startswith("【可新增字段】"):
                continue
            path = line.removeprefix("【可新增字段】").strip()
            if path:
                allowed.add(path)
        return allowed

    def _extract_old_field_value_from_context(self, context: str, path: str) -> str | None:
        root_key = self._extract_root_key(path)
        if not context or not root_key:
            return None

        field = path.split(".")[-1]
        match = re.search(rf"\[KV {re.escape(root_key)}\]\s*([^\n]+)", context)
        if not match:
            return None

        patch = KVPatch(match.group(1).strip())
        return patch.get_field(field)

    def _extract_root_key(self, path: str) -> str | None:
        if not path:
            return None
        parts = path.split(".")
        if len(parts) < 3:
            return None
        return ".".join(parts[:2])

    def _infer_fields_for_root(self, task: TaskExecution, root_key: str) -> list[str]:
        available_fields = self._extract_kv_fields(task.context, root_key)
        if not available_fields:
            return []

        ordered_blobs = [
            task.description,
            task.context,
            *task.execution_steps,
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
        for key in re.findall(r"\[KV\s+([A-Za-z][A-Za-z0-9_.]*)\]", text):
            if key not in seen:
                seen.add(key)
                ordered.append(key)
        return ordered

    def _extract_kv_fields(self, context: str, root_key: str) -> list[str]:
        if not context or not root_key:
            return []

        match = re.search(rf"\[KV {re.escape(root_key)}\]\s*([^\n]+)", context)
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
