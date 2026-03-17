"""
DeepPlannerAgent - 深度规划 Agent

输出可执行的 Markdown 执行稿。
"""
from __future__ import annotations

import uuid
import re
import json
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import BaseTool

from ..types import (
    PlannedTask,
)
from ..utils.logging import get_logger
from ..utils.script_parser import parse_task_summary
from ..skills import get_registry, Skill
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

    def get_system_prompt(self, mode: str = "plan") -> str:
        base_prompt = """你是 TRPG 规划助手，负责把 DM 指令转成可执行的 Markdown 执行稿，并在需要时生成受限补丁。

你的职责:
1. 分析 DM 的自然语言指令，识别行动者、目标、规则上下文
2. 使用工具查询必要的状态和规则
3. 产出一份完整执行稿，包含步骤、潜在线索和查询附录
4. 输出简洁、稳定、便于执行的主线步骤

重要提示:
- 所有数值必须标注来源（KV/RAG/确认）
- 不确定的信息标记为 [Needs Confirmation]
- 不要生成结构化 decision point
- Planner Hints 只能描述“可能插入的反应/连锁”，不能预先裁定结果
- Execution Steps 必须使用稳定的 step_id，并显式写出 status
- Execution Steps 的 `phase` 优先使用 `declare` / `action` / `resolution`
"""

        selected_skills = self.skills

        if not selected_skills:
            return base_prompt

        skills_content = "\n\n" + "=" * 50 + "\n\n".join(
            [f"## Skill: {s.name}\n{s.content}" for s in selected_skills]
        )
        return f"{base_prompt}\n\n## 可用的 Skills\n{skills_content}"

    def plan(self, user_input: str) -> list[PlannedTask]:
        self._logger.info("DeepPlannerAgent 分析指令", user_input=user_input)
        intent_type = self._detect_intent_type(user_input)

        if intent_type == "world_edit":
            return [self._build_world_edit_task(user_input)]

        final_message = self._run_prompt(TASK_TEMPLATE.format(user_input=user_input), mode="plan")
        content = self._coerce_content(final_message)
        return self._parse_markdown_task(content, user_input)

    def _run_prompt(self, task_prompt: str, mode: str = "plan", force_output_prompt: str | None = None) -> AIMessage:
        messages = [
            SystemMessage(content=self.get_system_prompt(mode=mode)),
            HumanMessage(content=task_prompt),
        ]
        return self._react_loop(messages, force_output_prompt=force_output_prompt or FORCE_OUTPUT_PROMPT)

    def _coerce_content(self, final_message: AIMessage) -> str:
        content_str = ""
        if isinstance(final_message.content, str):
            content_str = final_message.content
        elif isinstance(final_message.content, list):
            content_str = "\n".join(str(item) for item in final_message.content)
        if "<think>" in content_str:
            content_str = re.sub(r"<think>.*?</think>", "", content_str, flags=re.DOTALL).strip()
        self._logger.debug(f"Planner 原始输出:\n{content_str}")
        return content_str.strip()

    def _detect_intent_type(self, user_input: str) -> str:
        user_lower = user_input.lower()
        world_edit_keywords = [
            "set", "create", "delete", "modify", "update", "add", "remove",
            "spawn", "kill", "heal to", "set hp", "to full", "to max", "max hp",
            "设置", "创建", "删除", "修改", "更新", "添加", "移除", "生成",
            "杀死", "治疗到", "回满", "满血", "满状态", "设置生命", "直接", "立即",
            "world edit", "dm override",
        ]
        return "world_edit" if any(keyword in user_lower for keyword in world_edit_keywords) else "standard"

    def _build_world_edit_task(self, user_input: str) -> PlannedTask:
        return PlannedTask(
            task_id=f"task_{uuid.uuid4().hex[:8]}",
            description=user_input,
            context=user_input,
            actor="DM",
            target=None,
            source="dm",
            task_category="world_edit",
        )

    def _parse_markdown_task(self, content: str, original_input: str) -> list[PlannedTask]:
        cleaned, used_fallback = self._ensure_markdown_script(content, fallback=self._build_fallback_script(original_input))
        if used_fallback:
            self._logger.warning(
                "Planner 输出未通过 Markdown 执行稿校验，已回退到 fallback 脚本"
            )
        summary = parse_task_summary(cleaned)
        description = summary.get("description", original_input)
        actor = summary.get("actor", "未知")
        target = summary.get("target", "无")
        task_id = summary.get("task_id") or f"task_{uuid.uuid4().hex[:8]}"
        if target == "无":
            target = None
        return [
            PlannedTask(
                task_id=task_id,
                description=description,
                context=cleaned,
                actor=actor,
                target=target,
                source="dm",
                task_category="normal",
                task_status="pending",
            )
        ]

    def _ensure_markdown_script(self, content: str, fallback: str) -> tuple[str, bool]:
        stripped = content.strip()
        if "## Task Summary" in stripped and "## Execution Steps" in stripped:
            return stripped, False
        if stripped.startswith("```"):
            stripped = stripped.strip("`").strip()
        self._logger.debug(
            "未通过校验的 Planner 输出预览:\n{}",
            stripped[:2000] if stripped else "[empty]",
        )
        return fallback, True

    def _build_fallback_script(self, original_input: str) -> str:
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        return f"""## Task Summary
- Task ID: {task_id}
- Description: {original_input}
- Actor: 未知
- Target: 无

## Context
- [Needs Confirmation] 未能从 Planner 输出中解析到完整上下文，使用原始指令作为最小执行稿。

## Execution Steps
- [step_id: step_1] [status: pending] [phase: declare] [depends_on: none] [source: planner] 解析并执行指令 :: 根据现有上下文执行 `{original_input}`，必要时向 DM 请求确认。

## Planner Hints
- [hint_id: hint_none] [anchor: step_1] [when: none] [type: none] 当前未识别出明确的反应或连锁线索。

## Query Appendix
无
"""

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
