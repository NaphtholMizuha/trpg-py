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

    CACHEABLE_TOOLS = {"fetch_keys", "read", "search"}

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

    def plan(self, user_input: str) -> list[TaskExecution]:
        self._logger.info("DeepPlannerAgent 分析指令", user_input=user_input)
        intent_type, selected_skill = detect_intent_with_keywords(user_input)
        selected_skills = [selected_skill] if selected_skill is not None else self.skills

        messages = [
            SystemMessage(content=self.get_system_prompt(mode="plan", skills=selected_skills)),
            HumanMessage(content=TASK_TEMPLATE.format(user_input=user_input)),
        ]
        try:
            task = self._react_loop_structured(
                messages,
                TaskExecution,
                force_output_prompt=FORCE_OUTPUT_PROMPT,
            )
            return [self._normalize_task(self._ensure_task_id(task))]
        except Exception as exc:
            self._logger.warning("Planner structured output 失败，已回退", error=str(exc))
            return [self._build_fallback_task(user_input, intent_type=intent_type)]

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

        return task

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
