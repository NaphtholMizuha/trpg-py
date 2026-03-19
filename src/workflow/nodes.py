"""工作流节点函数 - 单步 planner / task_approval / executor / commiter。"""
from __future__ import annotations

import json
import os
import re

from langchain_core.messages import HumanMessage
from langgraph.graph import END
from langgraph.types import Command, interrupt

from ..types import (
    AgentState,
    DiscardedStateChange,
    ExecutionResult,
    ResolutionResult,
    ResolutionWindow,
    ResolutionWindowRun,
    StateChange,
    TaskExecution,
    WindowStatus,
    _build_task_state_snapshot,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


def _print_task_payload(title: str, task: TaskExecution) -> None:
    payload = task.model_dump(mode="json")
    print(f"\n🔎 {title}:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _extract_pending_confirmations(text: str | None) -> list[dict[str, str]]:
    if not text:
        return []

    confirmations: list[dict[str, str]] = []
    pattern = re.compile(
        r"\[Needs Confirmation\](?:\s*\[Default:\s*(?P<default>[^\]]+)\])?\s*(?P<question>[^\n]+)"
    )
    for match in pattern.finditer(text):
        question = match.group("question").strip()
        default = (match.group("default") or "").strip()
        if not default:
            default = "按最保守且不引入额外随机性的解释继续执行"
        confirmations.append({"question": question, "default": default})
    return confirmations


def _extract_confirmation_lines(text: str | None) -> list[str]:
    if not text:
        return []
    return [
        line.strip()
        for line in text.splitlines()
        if "[Needs Confirmation]" in line
    ]


def _apply_auto_confirm_defaults(task: TaskExecution) -> None:
    confirmations = _extract_pending_confirmations(task.context)
    if not confirmations:
        return
    lines = [task.dm_notes.strip()] if task.dm_notes else []
    for item in confirmations:
        lines.append(f"[Auto Confirmation] {item['question']} -> {item['default']}")
    task.dm_notes = "\n".join(line for line in lines if line).strip()


def _apply_modify_suggestion(task: TaskExecution, suggestion: str | None) -> None:
    suggestion_text = (suggestion or "").strip()
    if not suggestion_text:
        return

    dm_override = f"[DM Override] {suggestion_text}"
    notes = [task.dm_notes.strip()] if task.dm_notes else []
    if dm_override not in notes:
        notes.append(dm_override)
    task.dm_notes = "\n".join(line for line in notes if line).strip()

    override_context = (
        f"【DM裁定】{suggestion_text}。此裁定优先于上文默认规则、待确认项和执行步骤中的冲突内容。"
    )
    context_lines = task.context.splitlines() if task.context else []
    if override_context not in context_lines:
        context_lines.append(override_context)
    task.context = "\n".join(line for line in context_lines if line).strip()

    # DM 已回答待确认项后，当前任务上下文应视为完整，不再保留旧的待确认占位。
    resolved_lines = [
        line for line in task.context.splitlines()
        if "[Needs Confirmation]" not in line
    ]
    if override_context not in resolved_lines:
        resolved_lines.append(override_context)
    task.context = "\n".join(line for line in resolved_lines if line).strip()

    override_step = f"优先采用DM裁定：{suggestion_text}；若与其他步骤冲突，以此裁定为准。"
    execution_steps = [
        step for step in (task.execution_steps or [])
        if "[Needs Confirmation]" not in step and "确认采用默认裁定" not in step
    ]
    if override_step not in execution_steps:
        execution_steps.insert(0, override_step)
    task.execution_steps = execution_steps


def _enqueue_task(state: AgentState, task: TaskExecution) -> None:
    queue = state.get("task_queue", [])
    queue.append(task)
    print(f"\n⬇️  入队任务: {task.description[:50]}...")
    _print_task_payload("Planner 产出的完整 TaskExecution", task)
    state["task_queue"] = queue
    print(f"   队列长度: {len(queue)} 个任务")


def _extract_window_shared_context(context: str) -> list[str]:
    """从 task context 中抽取适合 resolver 复用的共享上下文。"""
    if not context:
        return []

    seen: set[str] = set()
    lines: list[str] = []
    for raw_line in context.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if not (
            "[KV " in line
            or "[RAG " in line
            or "[规则" in line
            or "[Rule" in line
        ):
            continue
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return lines


def _extract_task_shared_context(task: TaskExecution) -> list[str]:
    return _extract_window_shared_context(task.context)


def _merge_window_shared_context(window: ResolutionWindow, task: TaskExecution) -> None:
    existing = list(window.shared_context or [])
    seen = set(existing)
    for line in _extract_task_shared_context(task):
        if line in seen:
            continue
        seen.add(line)
        existing.append(line)
    window.shared_context = existing


def _merge_window_state_snapshot(window: ResolutionWindow, task: TaskExecution) -> None:
    existing = dict(window.state_snapshot or {})
    existing.update(_build_task_state_snapshot(task))
    window.state_snapshot = existing


def _next_window_id(state: AgentState) -> str:
    counter = int(state.get("window_counter", 0)) + 1
    state["window_counter"] = counter
    return f"window_{counter:03d}"


def _default_priority(window: ResolutionWindow) -> int:
    if not window.runs:
        return 10
    return min(run.priority for run in window.runs) - 1


def _coerce_priority(raw_priority: object, window: ResolutionWindow) -> int:
    if isinstance(raw_priority, int):
        return raw_priority
    if isinstance(raw_priority, str):
        try:
            return int(raw_priority.strip())
        except ValueError:
            pass
    return _default_priority(window)


def _build_window_run(
    task: TaskExecution,
    result: ExecutionResult,
    window: ResolutionWindow,
    *,
    priority: int | None = None,
) -> ResolutionWindowRun:
    return ResolutionWindowRun.from_task_and_result(
        task,
        result,
        order=len(window.runs),
        priority=priority if priority is not None else _default_priority(window),
    )


def _ensure_active_window(
    state: AgentState,
    task: TaskExecution,
    result: ExecutionResult,
) -> ResolutionWindow:
    active_window = state.get("active_window")
    if active_window is not None:
        return active_window

    active_window = ResolutionWindow(
        window_id=_next_window_id(state),
        root_task_id=task.task_id,
        root_description=task.description,
        status=WindowStatus.OPEN,
        shared_context=_extract_task_shared_context(task),
        state_snapshot=_build_task_state_snapshot(task),
        runs=[],
    )
    state["active_window"] = active_window
    return active_window


def _materialize_resolution(window: ResolutionWindow) -> ResolutionResult:
    """最小 resolver：按 priority/order 排序后，对同 path 采用后者覆盖。"""
    sorted_runs = sorted(window.runs, key=lambda run: (run.priority, run.order))
    final_by_path: dict[str, StateChange] = {}
    discarded: list[DiscardedStateChange] = []

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
                        discarded_by=f"resolver:{window.window_id}",
                        reason="同一路径字段变更被同窗口内更晚处理的结果覆盖。",
                    )
                )
            final_by_path[change.path] = StateChange(
                path=change.path,
                old_value=change.old_value,
                new_value=change.new_value,
                operation=change.operation,
                source=f"resolver:{window.window_id}",
            )

    return ResolutionResult(
        window_id=window.window_id,
        final_field_changes=list(final_by_path.values()),
        discarded_field_changes=discarded,
        resolution_summary=(
            f"resolver 收到 {len(window.runs)} 个 run，"
            f"产出 {len(final_by_path)} 个最终字段变更。"
        ),
        dm_suggestions=["若本窗口结算后引发新的规则问题，请由 DM 决定是否开启下一窗口。"],
    )


def _materialize_single_run_resolution(window: ResolutionWindow) -> ResolutionResult:
    """单 run 窗口直接收敛，无需调用 resolver agent。"""
    if len(window.runs) != 1:
        return _materialize_resolution(window)

    run = window.runs[0]
    resolver_source = f"resolver:{window.window_id}"
    final_changes = [
        StateChange(
            path=change.path,
            old_value=change.old_value,
            new_value=change.new_value,
            operation=change.operation,
            source=resolver_source,
        )
        for change in run.field_changes
    ]

    return ResolutionResult(
        window_id=window.window_id,
        final_field_changes=final_changes,
        discarded_field_changes=[],
        resolution_summary=(
            f"本结算窗口仅包含 1 个 run，直接采用该 run 的 {len(final_changes)} 个字段变更，无需进入 resolver 合并。"
        ),
        dm_suggestions=[],
    )


def create_planner_node(planner_agent):
    """创建规划节点。"""

    def planner_node(state: AgentState) -> Command:
        messages = state["messages"]
        current_task = state.get("_current_task")
        queue = state.get("task_queue", [])
        planned_message_count = state.get("_planned_message_count", 0)

        print(f"\n[planner] 进入: queue={len(queue)}")

        if current_task is not None:
            print(f"   当前任务完成: {current_task.description[:40]}...")
            state["_current_task"] = None

        last_message = messages[-1] if messages else None
        if (
            isinstance(last_message, HumanMessage)
            and not queue
            and not current_task
            and len(messages) > planned_message_count
        ):
            user_input = last_message.content
            print(f"\n🎮 DM: {user_input}")
            tasks = planner_agent.plan(user_input)
            for task in tasks:
                _enqueue_task(state, task)
            state["_planned_message_count"] = len(messages)

        queue = state.get("task_queue", [])
        state["task_queue"] = queue
        if queue:
            task = queue.pop(0)
            state["task_queue"] = queue
            state["_current_task"] = task
            print(f"\n📋 出队任务: {task.description[:50]}...")
            _print_task_payload("即将发送到 Executor 的 TaskExecution", task)
            return Command(goto="task_approval", update=state)

        print("✅ 所有任务执行完成")
        return Command(goto=END, update=state)

    return planner_node


def create_task_approval_node():
    """创建任务审批节点。"""

    def task_approval_node(state: AgentState) -> Command:
        task = state.get("_current_task")
        if not task:
            return Command(goto="planner", update=state)

        print(f"\n{'=' * 50}")
        print("⏸️  任务审批")
        print(f"{'=' * 50}")
        print(f"任务: {task.description}")
        print(f"类型: {task.task_category}")
        if task.context:
            print(f"\n上下文预览 (前500字符):\n  {task.context[:500]}...")
        if task.execution_steps:
            print("\n完整 execution_steps:")
            for idx, step in enumerate(task.execution_steps, start=1):
                print(f"  {idx}. {step}")
        confirmations = _extract_pending_confirmations(task.context)
        confirmation_lines = _extract_confirmation_lines(task.context)
        if confirmation_lines:
            print("\n待确认原文:")
            for line in confirmation_lines:
                print(f"  {line}")
        if confirmations:
            print("\n待确认默认项:")
            for item in confirmations:
                print(f"  - {item['question']}")
                print(f"    默认: {item['default']}")

        if os.getenv("TRPG_AUTO_CONFIRM") == "1":
            _apply_auto_confirm_defaults(task)
            print("\n🤖 [自动确认模式] 已自动批准")
            return Command(goto="executor", update=state)

        result = interrupt(
            {
                "type": "task_approval",
                "task": {
                    "task_id": task.task_id,
                    "description": task.description,
                    "task_category": task.task_category,
                    "actor": task.actor,
                    "target": task.target,
                    "context_preview": task.context[:500] if task.context else "",
                },
                "options": ["approve", "reject", "modify"],
            }
        )
        action = result.get("action", "approve")
        if action == "reject":
            state["_current_task"] = None
            return Command(goto="planner", update=state)
        if action == "modify":
            suggestion = str(result.get("suggestion", "")).strip()
            if suggestion:
                _apply_modify_suggestion(task, suggestion)
                return Command(goto="task_approval", update=state)
        return Command(goto="executor", update=state)

    return task_approval_node


def create_executor_node(executor_agent):
    """创建执行节点。"""

    def executor_node(state: AgentState) -> Command:
        task = state.get("_current_task")
        if not task:
            return Command(goto="planner", update=state)

        print("\n🎯 Executor: 开始执行任务")
        print(f"   {task.description}")
        print(f"   类型: {task.task_category}")
        _print_task_payload("Executor 收到的 TaskExecution", task)

        result: ExecutionResult = executor_agent.execute(task)
        state["_execution_result"] = result

        print("\n🧾 Executor 产出的 ExecutionResult:")
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))

        return Command(goto="window_review", update=state)

    return executor_node


def create_window_review_node():
    """创建结算窗口检查节点。"""

    def window_review_node(state: AgentState) -> Command:
        task = state.get("_current_task")
        result = state.get("_execution_result")
        if not task or not result:
            return Command(goto="planner", update=state)

        active_window = _ensure_active_window(state, task, result)
        _merge_window_shared_context(active_window, task)
        _merge_window_state_snapshot(active_window, task)
        if not any(run.task_id == result.task_id for run in active_window.runs):
            pending_priority = state.get("pending_window_priority")
            priority = pending_priority if pending_priority is not None else (10 if not active_window.runs else _default_priority(active_window))
            active_window.runs.append(_build_window_run(task, result, active_window, priority=priority))
            state["pending_window_priority"] = None

        active_window.status = WindowStatus.OPEN

        latest_run = active_window.runs[-1]
        print("\n🪟 Window Review: 检查当前结算窗口")
        print(f"   窗口: {active_window.window_id}")
        print(f"   当前 run 数: {len(active_window.runs)}")
        print("   最新 run:")
        print(json.dumps(latest_run.model_dump(mode="json"), ensure_ascii=False, indent=2))

        if os.getenv("TRPG_AUTO_CONFIRM") == "1":
            active_window.status = WindowStatus.READY
            state["pending_resolution"] = None
            print("\n🤖 [自动确认模式] 默认关闭当前窗口，进入 resolver")
            return Command(goto="resolver", update=state)

        review_result = interrupt(
            {
                "type": "resolution_window_review",
                "window_id": active_window.window_id,
                "root_description": active_window.root_description,
                "latest_run": {
                    "task_id": latest_run.task_id,
                    "description": latest_run.description,
                    "narration": latest_run.narration,
                },
                "default_priority": _default_priority(active_window),
                "options": ["append_same_window_action", "close_window"],
            }
        )

        action = review_result.get("action", "close_window")
        if action == "append_same_window_action":
            user_input = str(review_result.get("user_input", "")).strip()
            if not user_input:
                print("⚠️  未提供追加动作内容，将直接关闭当前窗口")
                action = "close_window"
            else:
                priority = _coerce_priority(review_result.get("priority"), active_window)
                state["_current_task"] = None
                state["_execution_result"] = None
                state["pending_window_priority"] = priority
                state["messages"] = state.get("messages", []) + [HumanMessage(content=user_input)]
                print(f"   追加同窗口动作: {user_input}")
                print(f"   该动作默认/指定 priority: {priority}")
                return Command(goto="planner", update=state)

        active_window.status = WindowStatus.READY
        return Command(goto="resolver", update=state)

    return window_review_node


def create_resolver_node(resolver_agent):
    """创建 resolver 节点。"""

    def resolver_node(state: AgentState) -> Command:
        active_window = state.get("active_window")
        if not active_window:
            return Command(goto="planner", update=state)

        print("\n🧩 Resolver: 开始合并当前窗口")
        print(json.dumps(active_window.model_dump(mode="json"), ensure_ascii=False, indent=2))

        if len(active_window.runs) == 1:
            resolution = _materialize_single_run_resolution(active_window)
            print("   单 run 窗口，跳过 resolver agent，直接采用当前 run 结果。")
        else:
            resolution = resolver_agent.resolve(active_window)
        state["pending_resolution"] = resolution
        active_window.status = WindowStatus.RESOLVED

        print("\n🧾 Resolver 产出的 ResolutionResult:")
        print(json.dumps(resolution.model_dump(mode="json"), ensure_ascii=False, indent=2))

        return Command(goto="commiter", update=state)

    return resolver_node


def create_commiter_node(write_fields_tool):
    """创建固定写回节点。"""

    def commiter_node(state: AgentState) -> Command:
        task = state.get("_current_task")
        result = state.get("_execution_result")
        resolution = state.get("pending_resolution")

        if not task and not resolution:
            return Command(goto="planner", update=state)

        print("\n🗂️ Commiter: 开始处理 field_changes")

        if resolution is not None:
            payload_changes = []
            for change in resolution.final_field_changes:
                parts = change.path.rsplit(".", 1)
                if len(parts) != 2:
                    print(f"⚠️  跳过写回 {change.path}: 只接受字段级路径，格式应为 Key.Field")
                    continue
                key, field = parts
                current_value = write_fields_tool.store.get(key)
                if change.operation.value in {"MOD", "DEL"} and current_value is None:
                    print(f"⚠️  跳过写回 {change.path}: 基础 key 不存在于当前 world-state")
                    continue
                payload_changes.append(
                    {
                        "path": change.path,
                        "old_value": change.old_value,
                        "new_value": change.new_value,
                        "operation": change.operation.value,
                    }
                )
            payload = {"field_changes": payload_changes}
            print("   写回 payload:")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            if not payload_changes:
                print("   写回结果:")
                print("未应用任何变更")
                print("📝 已应用 0 个状态变更")
            else:
                tool_output = write_fields_tool.invoke(payload)
                print("   写回结果:")
                print(tool_output)
                committed = [
                    change
                    for change in resolution.final_field_changes
                    if any(fc["path"] == change.path for fc in payload_changes)
                ]
                state["changes"] = state.get("changes", []) + committed
                applied_count = sum(1 for line in str(tool_output).splitlines() if line.startswith("✓ "))
                print(f"📝 已应用 {applied_count} 个状态变更")

            state["pending_resolution"] = None
            state["active_window"] = None
            state["pending_window_priority"] = None
            state["_execution_result"] = None
            state["_current_task"] = None
            return Command(goto="planner", update=state)

        if not task or not result:
            return Command(goto="planner", update=state)

        if result.field_changes:
            payload_changes = []
            for change in result.field_changes:
                parts = change.path.rsplit(".", 1)
                if len(parts) != 2:
                    print(f"⚠️  跳过写回 {change.path}: 只接受字段级路径，格式应为 Key.Field")
                    continue
                key, field = parts
                current_value = write_fields_tool.store.get(key)
                if change.operation.value in {"MOD", "DEL"} and current_value is None:
                    print(f"⚠️  跳过写回 {change.path}: 基础 key 不存在于当前 world-state")
                    continue
                payload_changes.append(
                    {
                        "path": change.path,
                        "old_value": change.old_value,
                        "new_value": change.new_value,
                        "operation": change.operation.value,
                    }
                )
            payload = {"field_changes": payload_changes}
            print("   写回 payload:")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            if not payload_changes:
                print("   写回结果:")
                print("未应用任何变更")
                print("📝 已应用 0 个状态变更")
                _enqueue_triggered_chains(state, result, task)
                if not result.success:
                    logger.warning("Executor 未产生有效结果", task_id=task.task_id, narration=result.narration)
                state["_execution_result"] = None
                state["_current_task"] = None
                return Command(goto="planner", update=state)
            tool_output = write_fields_tool.invoke(payload)
            print("   写回结果:")
            print(tool_output)
            committed = [change for change in result.field_changes if any(fc["path"] == change.path for fc in payload_changes)]
            state["changes"] = state.get("changes", []) + committed
            applied_count = sum(1 for line in str(tool_output).splitlines() if line.startswith("✓ "))
            print(f"📝 已应用 {applied_count} 个状态变更")
        else:
            print("   无字段变更需要写回")

        _enqueue_triggered_chains(state, result, task)

        if not result.success:
            logger.warning("Executor 未产生有效结果", task_id=task.task_id, narration=result.narration)

        state["_execution_result"] = None
        state["_current_task"] = None
        state["pending_window_priority"] = None
        return Command(goto="planner", update=state)

    return commiter_node


def _enqueue_triggered_chains(state: AgentState, result: ExecutionResult, task: TaskExecution) -> None:
    if not result.triggered_chains:
        return
    for chain in result.triggered_chains:
        chain_task = TaskExecution(
            task_id=chain.task_id or f"chain_{task.task_id}_{len(state.get('task_queue', []))}",
            description=chain.description or "连锁任务",
            context=chain.context or chain.description or "连锁任务",
            actor=chain.actor,
            target=chain.target,
            source="chain",
            dm_notes=chain.dm_notes,
            task_category=chain.task_category,
        )
        _enqueue_task(state, chain_task)
