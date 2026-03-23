"""ResolverAgent - 同窗口结果合并 Agent。"""
from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from ..config import RESOLVER_SYSTEM_PROMPT
from ..types import (
    DiscardedStateChange,
    ResolutionResult,
    ResolutionWindow,
    StateChange,
)
from ..utils.logging import get_logger
from .base import BaseAgent

logger = get_logger(__name__)

_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"
TASK_TEMPLATE = (_PROMPT_DIR / "resolver_task.md").read_text(encoding="utf-8")
FORCE_OUTPUT_PROMPT = (_PROMPT_DIR / "force_output" / "resolver.txt").read_text(encoding="utf-8")


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
                force_output_prompt=FORCE_OUTPUT_PROMPT,
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

        result.final_resource_costs = self._sanitize_final_bucket(result.final_resource_costs, allowed_paths, resolver_source)
        result.final_primary_effects = self._sanitize_final_bucket(result.final_primary_effects, allowed_paths, resolver_source)
        result.final_contingent_effects = self._sanitize_final_bucket(result.final_contingent_effects, allowed_paths, resolver_source)
        if not any((result.final_resource_costs, result.final_primary_effects, result.final_contingent_effects)) and result.final_field_changes:
            result.final_primary_effects = self._sanitize_final_bucket(result.final_field_changes, allowed_paths, resolver_source)

        result.discarded_resource_costs = self._sanitize_discarded_bucket(result.discarded_resource_costs, allowed_paths, resolver_source)
        result.discarded_primary_effects = self._sanitize_discarded_bucket(result.discarded_primary_effects, allowed_paths, resolver_source)
        result.discarded_contingent_effects = self._sanitize_discarded_bucket(result.discarded_contingent_effects, allowed_paths, resolver_source)
        if not any(
            (
                result.discarded_resource_costs,
                result.discarded_primary_effects,
                result.discarded_contingent_effects,
            )
        ) and result.discarded_field_changes:
            result.discarded_primary_effects = self._sanitize_discarded_bucket(result.discarded_field_changes, allowed_paths, resolver_source)

        result.final_field_changes = [
            *result.final_resource_costs,
            *result.final_primary_effects,
            *result.final_contingent_effects,
        ]
        result.discarded_field_changes = [
            *result.discarded_resource_costs,
            *result.discarded_primary_effects,
            *result.discarded_contingent_effects,
        ]

        self._discard_conflicting_final_changes(result)
        self._promote_cancelled_resource_costs_to_discarded(result, window)

        if not result.resolution_summary:
            result.resolution_summary = "resolver 完成了当前结算窗口的合并裁决。"

        result.dm_suggestions = [item for item in (result.dm_suggestions or []) if item]
        return result

    def _sanitize_final_bucket(
        self,
        changes: list[StateChange],
        allowed_paths: set[str],
        resolver_source: str,
    ) -> list[StateChange]:
        sanitized: list[StateChange] = []
        for change in changes:
            if allowed_paths and change.path not in allowed_paths:
                continue
            change.source = resolver_source
            sanitized.append(change)
        return sanitized

    def _sanitize_discarded_bucket(
        self,
        changes: list[DiscardedStateChange],
        allowed_paths: set[str],
        resolver_source: str,
    ) -> list[DiscardedStateChange]:
        sanitized: list[DiscardedStateChange] = []
        for change in changes:
            if allowed_paths and change.path not in allowed_paths:
                continue
            if not change.discarded_by:
                change.discarded_by = resolver_source
            if not change.reason:
                change.reason = "被 resolver 判定为在当前结算窗口内不生效。"
            sanitized.append(change)
        return sanitized

    def _discard_conflicting_final_changes(self, result: ResolutionResult) -> None:
        discarded_paths = {change.path for change in result.discarded_field_changes if change.path}
        if not discarded_paths:
            return

        result.final_resource_costs = [
            change for change in result.final_resource_costs if change.path not in discarded_paths
        ]
        result.final_primary_effects = [
            change for change in result.final_primary_effects if change.path not in discarded_paths
        ]
        result.final_contingent_effects = [
            change for change in result.final_contingent_effects if change.path not in discarded_paths
        ]
        result.final_field_changes = [
            *result.final_resource_costs,
            *result.final_primary_effects,
            *result.final_contingent_effects,
        ]

    def _promote_cancelled_resource_costs_to_discarded(
        self,
        result: ResolutionResult,
        window: ResolutionWindow,
    ) -> None:
        if result.discarded_resource_costs or not result.final_resource_costs:
            return
        if not self._window_indicates_cancellation(window, result):
            return

        promoted: list[DiscardedStateChange] = []
        for change in result.final_resource_costs:
            promoted.append(
                DiscardedStateChange(
                    path=change.path,
                    old_value=change.old_value,
                    new_value=change.new_value,
                    operation=change.operation,
                    source=change.source,
                    discarded_by=window.root_task_id or f"resolver:{window.window_id}",
                    reason="窗口上下文表明该动作被取消，相关资源消耗不应生效。",
                )
            )

        result.discarded_resource_costs = promoted
        result.final_resource_costs = []
        result.final_field_changes = [
            *result.final_resource_costs,
            *result.final_primary_effects,
            *result.final_contingent_effects,
        ]
        result.discarded_field_changes = [
            *result.discarded_resource_costs,
            *result.discarded_primary_effects,
            *result.discarded_contingent_effects,
        ]

    def _window_indicates_cancellation(
        self,
        window: ResolutionWindow,
        result: ResolutionResult,
    ) -> bool:
        text = "\n".join(
            item
            for item in (
                window.root_description,
                result.resolution_summary,
                *window.shared_context,
                *(run.description for run in window.runs),
                *(run.narration for run in window.runs),
            )
            if item
        )
        cancellation_keywords = (
            "法术反制",
            "被反制",
            "取消",
            "无效",
            "未生效",
            "失效",
            "counterspell",
            "cancelled",
            "negated",
        )
        return any(keyword in text for keyword in cancellation_keywords)

    def _is_actionable_result(self, result: ResolutionResult) -> bool:
        return any(
            (
                result.final_resource_costs,
                result.final_primary_effects,
                result.final_contingent_effects,
                result.final_field_changes,
                result.discarded_resource_costs,
                result.discarded_primary_effects,
                result.discarded_contingent_effects,
                result.discarded_field_changes,
                (result.resolution_summary or "").strip(),
                result.dm_suggestions,
            )
        )

    def _build_fallback_result(self, window: ResolutionWindow) -> ResolutionResult:
        """保底 resolver：按 priority/order 排序后，对同 path 采用后者覆盖。"""
        sorted_runs = sorted(window.runs, key=lambda run: (run.priority, run.order))
        resolver_source = f"resolver:{window.window_id}"
        final_resource_by_path: dict[str, StateChange] = {}
        final_primary_by_path: dict[str, StateChange] = {}
        final_contingent_by_path: dict[str, StateChange] = {}
        discarded_resource_costs: list[DiscardedStateChange] = []
        discarded_primary_effects: list[DiscardedStateChange] = []
        discarded_contingent_effects: list[DiscardedStateChange] = []

        for run in sorted_runs:
            for change in run.resource_costs:
                previous = final_resource_by_path.get(change.path)
                if previous is not None:
                    discarded_resource_costs.append(
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
                final_resource_by_path[change.path] = StateChange(
                    path=change.path,
                    old_value=change.old_value,
                    new_value=change.new_value,
                    operation=change.operation,
                    source=resolver_source,
                )
            for change in run.primary_effects:
                previous = final_primary_by_path.get(change.path)
                if previous is not None:
                    discarded_primary_effects.append(
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
                final_primary_by_path[change.path] = StateChange(
                    path=change.path,
                    old_value=change.old_value,
                    new_value=change.new_value,
                    operation=change.operation,
                    source=resolver_source,
                )
            for change in run.contingent_effects:
                previous = final_contingent_by_path.get(change.path)
                if previous is not None:
                    discarded_contingent_effects.append(
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
                final_contingent_by_path[change.path] = StateChange(
                    path=change.path,
                    old_value=change.old_value,
                    new_value=change.new_value,
                    operation=change.operation,
                    source=resolver_source,
                )

        return ResolutionResult(
            window_id=window.window_id,
            final_resource_costs=list(final_resource_by_path.values()),
            final_primary_effects=list(final_primary_by_path.values()),
            final_contingent_effects=list(final_contingent_by_path.values()),
            discarded_resource_costs=discarded_resource_costs,
            discarded_primary_effects=discarded_primary_effects,
            discarded_contingent_effects=discarded_contingent_effects,
            resolution_summary=(
                f"resolver fallback 收到 {len(window.runs)} 个 run，"
                f"产出 {len(final_resource_by_path) + len(final_primary_by_path) + len(final_contingent_by_path)} 个最终字段变更。"
            ),
            dm_suggestions=["若本窗口结算后引发新的规则问题，请由 DM 决定是否开启下一窗口。"],
        )
