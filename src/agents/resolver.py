"""ResolverAgent - 同窗口结果合并 Agent。"""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from ..prompting import load_prompt
from ..types import (
    DiscardedStateChange,
    ResolutionResult,
    ResolutionWindow,
    StateChange,
)
from ..utils.logging import get_logger
from .base import BaseAgent

logger = get_logger(__name__)

RESOLVER_SYSTEM_PROMPT = load_prompt("resolver.md")
TASK_TEMPLATE = load_prompt("resolver_task.md")


class ResolverAgent(BaseAgent):
    """对同一结算窗口内的多个 run 做合并裁决。"""

    SYSTEM_PROMPT = RESOLVER_SYSTEM_PROMPT
    ALLOWED_TOOLS = {"read", "search", "fetch_keys"}

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
        tools: list[BaseTool] | None = None,
    ):
        filtered_tools = None
        if tools is not None:
            filtered_tools = [t for t in tools if t.name in self.ALLOWED_TOOLS]
        super().__init__(model, api_key, base_url, filtered_tools, max_iterations=4)

    def get_system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def resolve(self, window: ResolutionWindow) -> ResolutionResult:
        logger.info(
            "ResolverAgent 开始合并窗口",
            window_id=window.window_id,
            runs=len(window.runs),
        )
        search_tool = self.tools.get("search")
        if search_tool is not None and hasattr(search_tool, "reset_session"):
            search_tool.reset_session()

        task_prompt = TASK_TEMPLATE.format(
            window_id=window.window_id,
            root_task_id=window.root_task_id or "无",
            root_description=window.root_description,
            status=window.status.value,
            path_hints=self._build_path_hints(window),
            shared_context=self._format_shared_context(window),
            window_json=json.dumps(window.model_dump(mode="json"), ensure_ascii=False, indent=2),
        )

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=task_prompt),
        ]

        try:
            result = self._invoke_agent(
                messages=messages,
                response_format=ResolutionResult,
            )
        except Exception as exc:
            logger.exception(f"Resolver structured output 失败: {exc}")
            return self._build_fallback_result(window)

        result.window_id = window.window_id
        result = self._sanitize_result(result, window)
        if not self._is_actionable_result(result):
            logger.warning("Resolver 输出为空结果，将回退到保底合并", window_id=window.window_id)
            return self._build_fallback_result(window)
        return result

    def _format_shared_context(self, window: ResolutionWindow) -> str:
        if not window.shared_context:
            return "- 无"
        return "\n".join(f"- {line}" for line in window.shared_context)

    def _build_path_hints(self, window: ResolutionWindow) -> str:
        paths = sorted(self._collect_allowed_paths(window))
        if not paths:
            return "- 无已知字段路径"
        return "\n".join(f"- {path}" for path in paths)

    def _collect_allowed_paths(self, window: ResolutionWindow) -> set[str]:
        allowed_paths: set[str] = set()
        for run in window.runs:
            for change in run.field_changes:
                if change.path:
                    allowed_paths.add(change.path)
        return allowed_paths

    def _sanitize_result(self, result: ResolutionResult, window: ResolutionWindow) -> ResolutionResult:
        allowed_paths = self._collect_allowed_paths(window)
        resolver_source = f"resolver:{window.window_id}"

        sanitized_final: list[StateChange] = []
        for change in result.final_field_changes:
            if allowed_paths and change.path not in allowed_paths:
                continue
            change.source = resolver_source
            sanitized_final.append(change)
        result.final_field_changes = sanitized_final

        sanitized_discarded: list[DiscardedStateChange] = []
        for change in result.discarded_field_changes:
            if allowed_paths and change.path not in allowed_paths:
                continue
            if not change.discarded_by:
                change.discarded_by = resolver_source
            if not change.reason:
                change.reason = "被 resolver 判定为在当前结算窗口内不生效。"
            sanitized_discarded.append(change)
        result.discarded_field_changes = sanitized_discarded

        if not result.resolution_summary:
            result.resolution_summary = "resolver 完成了当前结算窗口的合并裁决。"

        result.dm_suggestions = [item for item in (result.dm_suggestions or []) if item]
        return result

    def _is_actionable_result(self, result: ResolutionResult) -> bool:
        return any(
            (
                result.final_field_changes,
                result.discarded_field_changes,
                (result.resolution_summary or "").strip(),
                result.dm_suggestions,
            )
        )

    def _build_fallback_result(self, window: ResolutionWindow) -> ResolutionResult:
        """保底 resolver：按 priority/order 排序后，对同 path 采用后者覆盖。"""
        sorted_runs = sorted(window.runs, key=lambda run: (run.priority, run.order))
        final_by_path: dict[str, StateChange] = {}
        discarded: list[DiscardedStateChange] = []
        resolver_source = f"resolver:{window.window_id}"

        for run in sorted_runs:
            for change in run.field_changes:
                previous = final_by_path.get(change.path)
                if previous is not None:
                    discarded.append(
                        DiscardedStateChange(
                            path=previous.path,
                            old_value=previous.old_value,
                            new_value=previous.new_value,
                            operation=previous.operation,
                            source=previous.source,
                            discarded_by=resolver_source,
                            reason="同一路径字段变更被同窗口内更晚处理的结果覆盖。",
                        )
                    )
                final_by_path[change.path] = StateChange(
                    path=change.path,
                    old_value=change.old_value,
                    new_value=change.new_value,
                    operation=change.operation,
                    source=resolver_source,
                )

        return ResolutionResult(
            window_id=window.window_id,
            final_field_changes=list(final_by_path.values()),
            discarded_field_changes=discarded,
            resolution_summary=(
                f"resolver fallback 收到 {len(window.runs)} 个 run，"
                f"产出 {len(final_by_path)} 个最终字段变更。"
            ),
            dm_suggestions=["若本窗口结算后引发新的规则问题，请由 DM 决定是否开启下一窗口。"],
        )
