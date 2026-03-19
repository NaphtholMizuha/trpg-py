"""ExecutorAgent - 单步执行 Agent。"""
from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from ..prompting import load_prompt
from ..types import ExecutionResult, TaskExecution
from ..utils.logging import get_logger
from ..utils.kv_patch import KVPatch
from ..types import StateChange, Operation
from .base import BaseAgent

logger = get_logger(__name__)

EXECUTOR_SYSTEM_PROMPT = load_prompt("executor.md")
TASK_TEMPLATE = load_prompt("executor_task.md")


class ExecutorAgent(BaseAgent):
    """执行单个任务，并返回状态更新。"""

    SYSTEM_PROMPT = EXECUTOR_SYSTEM_PROMPT
    ALLOWED_TOOLS = {"evaluate"}

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

    def _build_key_hints(self, task: TaskExecution) -> str:
        actor = (task.actor or "").strip()
        target = (task.target or "").strip()
        context_keys = self._extract_context_keys(task.context)
        write_targets = task.write_targets or []
        lines = [
            "精确 world-state key 规则:",
            "- 信息源优先级固定为：`DM批注 / DM裁定` > `KV` > `RAG`",
            "- `field_changes` 里只能写入上下文中已经出现过的 world-state key，不能翻译、不能改拼写、不能自造别名。",
            "- 不要调用写入工具；你只负责返回 `field_changes`，后续会由 commiter 节点统一写回。",
            "- 如果 `DM批注` 中已有 `[Auto Confirmation] ... -> 视为命中/视为攻击成功/视为失败` 这类裁定，就把它当作既成事实，不要再次为同一件事掷骰。",
            "- 如果 `KV` 与 `RAG` 冲突，优先相信 `KV` 中的当前状态；`RAG` 只用于补足规则，不用于覆盖当前世界状态。",
            "- 不要用 `evaluate` 读取 KV、解析 `4/4` 这类字符串、或计算 `Malik.spell_slots['1环'] - 1` 这种表达式。",
            "- 只有掷骰等随机结果才调用 `evaluate`；简单整数加减请直接根据上下文给出结果。",
            "- 只接受字段级修改，`path` 必须写成 `Key.Field`，例如 `Aldera.combat.HP`、`Malik.spell_slots.1环`。",
            "- 不允许整 key 覆盖；不要返回 `Aldera.combat` 或 `Malik.spell_slots` 这种 path。",
        ]
        if context_keys:
            lines.append(f"- 本轮允许引用的基础 key: {', '.join(context_keys)}")
        if write_targets:
            lines.append(f"- 本轮优先写回这些字段路径: {', '.join(write_targets)}")
        if actor:
            lines.append(f"- 行动者前缀固定为 `{actor}`")
            lines.append(f"- 行动者常用 key: `{actor}.combat`, `{actor}.spell_slots`, `{actor}.status`, `{actor}.spells`")
        if target:
            lines.append(f"- 目标前缀固定为 `{target}`")
            lines.append(f"- 目标常用 key: `{target}.combat`, `{target}.spell_slots`, `{target}.status`, `{target}.spells`")
        lines.append("- 错误示例: `马利克.spell_slots`, `艾尔德拉.combat`, `Eldra.combat`")
        return "\n".join(lines)

    def execute(self, task: TaskExecution) -> ExecutionResult:
        logger.info("ExecutorAgent 执行任务", task_id=task.task_id, description=task.description)

        task_prompt = TASK_TEMPLATE.format(
            task_id=task.task_id,
            description=task.description,
            execution_steps="\n".join(f"- {step}" for step in task.execution_steps) if task.execution_steps else "- 无",
            write_targets="\n".join(f"- {target}" for target in task.write_targets) if task.write_targets else "- 无",
            actor=task.actor,
            target=task.target,
            dm_notes=task.dm_notes or "无",
            context=task.context,
            key_hints=self._build_key_hints(task),
        )

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=task_prompt),
        ]
        tools_for_call = self._tools if self._task_requires_evaluate(task) else []
        try:
            result = self._invoke_agent(
                messages=messages,
                tools=tools_for_call,
                response_format=ExecutionResult,
            )
        except Exception as exc:
            logger.exception(f"Executor structured output 失败: {exc}")
            return self._build_fallback_result(task)

        result.task_id = task.task_id
        for change in result.field_changes:
            change.source = task.task_id

        result = self._sanitize_result(result, task)
        result = self._backfill_missing_changes(result, task)
        if not self._is_actionable_result(result):
            logger.warning("Executor 输出为空结果，将标记为 stalled", task_id=task.task_id)
            result.success = False
            result.narration = "executor_stalled"
        return result

    def _build_fallback_result(self, task: TaskExecution) -> ExecutionResult:
        return ExecutionResult(
            task_id=task.task_id,
            success=False,
            field_changes=[],
            narration="executor_stalled",
            triggered_chains=[],
        )

    def _is_actionable_result(self, result: ExecutionResult) -> bool:
        narration = (result.narration or "").strip()
        return any((result.field_changes, result.triggered_chains, narration, result.success))

    def _sanitize_result(self, result: ExecutionResult, task: TaskExecution) -> ExecutionResult:
        allowed_roots = set(self._extract_context_keys(task.context))
        allowed_targets = set(task.write_targets or [])
        allowed_additions = self._extract_allowed_additions(task.context)
        sanitized_changes = []
        for change in result.field_changes:
            root_key = self._extract_root_key(change.path)
            if allowed_targets and change.path not in allowed_targets:
                continue
            if allowed_roots and (not root_key or root_key not in allowed_roots):
                continue
            if not self._is_valid_world_state_change(change.path):
                continue
            current_field_value = self._extract_old_field_value_from_context(task.context, change.path)
            if not self._is_allowed_field_change(
                change.path,
                change.operation,
                current_field_value,
                allowed_additions,
            ):
                continue
            if not change.old_value:
                change.old_value = current_field_value
            if change.operation == Operation.ADD and current_field_value is not None:
                change.operation = Operation.MOD
            self._normalize_field_change_values(change, current_field_value)
            sanitized_changes.append(change)
        result.field_changes = sanitized_changes
        result.triggered_chains = [
            chain
            for chain in (result.triggered_chains or [])
            if getattr(chain, "description", "")
        ]
        return result

    def _extract_context_keys(self, context: str) -> list[str]:
        if not context:
            return []
        seen: set[str] = set()
        ordered: list[str] = []
        for key in re.findall(r"\[KV\s+([A-Za-z][A-Za-z0-9_.]*)\]", context):
            if key not in seen:
                seen.add(key)
                ordered.append(key)
        return ordered

    def _extract_root_key(self, path: str) -> str | None:
        if not path:
            return None
        parts = path.split(".")
        if len(parts) < 3:
            return None
        return ".".join(parts[:2])

    def _extract_old_field_value_from_context(self, context: str, path: str) -> str | None:
        root_key = self._extract_root_key(path)
        if not context or not root_key:
            return None
        field = path.split(".")[-1]
        pattern = rf"\[KV {re.escape(root_key)}\]\s*([^\n]+)"
        match = re.search(pattern, context)
        if not match:
            return None
        patch = KVPatch(match.group(1).strip())
        return patch.get_field(field)

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

    def _is_allowed_field_change(
        self,
        path: str,
        operation: Operation,
        current_field_value: str | None,
        allowed_additions: set[str],
    ) -> bool:
        root_key = self._extract_root_key(path)
        if not root_key:
            return False

        if operation in (Operation.MOD, Operation.DEL):
            return current_field_value is not None

        if operation != Operation.ADD:
            return False

        if current_field_value is not None:
            return True

        return path in allowed_additions

    def _task_requires_evaluate(self, task: TaskExecution) -> bool:
        text = f"{task.description}\n{task.context}\n{task.dm_notes or ''}"
        if re.search(r"\b\d+d\d+\b", text, re.IGNORECASE):
            return True
        random_keywords = (
            "掷骰",
            "伤害",
            "治疗",
            "检定",
            "豁免",
            "命中",
            "攻击",
            "先攻",
            "damage",
            "heal",
            "save",
            "check",
            "attack",
            "roll",
        )
        return any(keyword in text for keyword in random_keywords)

    def _is_valid_world_state_change(self, path: str) -> bool:
        return bool(path) and not path.startswith("task_") and self._extract_root_key(path) is not None

    def _normalize_field_change_values(self, change: StateChange, current_field_value: str | None) -> None:
        if not current_field_value:
            return

        field = change.path.split(".")[-1]
        if field == "HP":
            match = re.fullmatch(r"(-?\d+)/(\d+)", current_field_value)
            if match:
                hp_max = match.group(2)
                if change.old_value and re.fullmatch(r"-?\d+", change.old_value):
                    change.old_value = f"{max(int(change.old_value), 0)}/{hp_max}"
                if change.new_value and re.fullmatch(r"-?\d+", change.new_value):
                    change.new_value = f"{max(int(change.new_value), 0)}/{hp_max}"
        if re.fullmatch(r"\d+环", field):
            match = re.fullmatch(r"(\d+)/(\d+)", current_field_value)
            if match:
                slot_max = match.group(2)
                if change.old_value and re.fullmatch(r"-?\d+", change.old_value):
                    change.old_value = f"{max(int(change.old_value), 0)}/{slot_max}"
                if change.new_value and re.fullmatch(r"-?\d+", change.new_value):
                    change.new_value = f"{max(int(change.new_value), 0)}/{slot_max}"

    def _backfill_missing_changes(self, result: ExecutionResult, task: TaskExecution) -> ExecutionResult:
        if result.field_changes or not result.success or not task.write_targets:
            return result

        for target_path in task.write_targets:
            if not target_path.endswith(".HP"):
                continue
            current_hp = self._extract_old_field_value_from_context(task.context, target_path)
            if not current_hp:
                continue
            hp_match = re.fullmatch(r"(\d+)/(\d+)", current_hp)
            if not hp_match:
                continue
            current_value = int(hp_match.group(1))
            hp_max = int(hp_match.group(2))

            damage_match = re.search(r"造成了?\s*(\d+)\s*点", result.narration)
            down_to_match = re.search(r"(?:降至|减少至|生命值降至)\s*(-?\d+)", result.narration)

            if down_to_match:
                new_value = max(int(down_to_match.group(1)), 0)
            elif damage_match:
                new_value = max(current_value - int(damage_match.group(1)), 0)
            else:
                continue

            result.field_changes.append(
                StateChange(
                    path=target_path,
                    old_value=f"{current_value}/{hp_max}",
                    new_value=f"{new_value}/{hp_max}",
                    operation=Operation.MOD,
                    source=task.task_id,
                )
            )

        return result

    def run(self, task: TaskExecution) -> ExecutionResult:
        return self.execute(task)
