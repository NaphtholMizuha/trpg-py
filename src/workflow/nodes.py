"""工作流节点函数 - 单步 planner / task_approval / executor / commiter。"""
from __future__ import annotations

import json
import os
import re

from langchain_core.messages import HumanMessage
from langgraph.graph import END
from langgraph.types import Command, interrupt

from ..types import AgentState, ExecutionResult, TaskExecution
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


def _apply_auto_confirm_defaults(task: TaskExecution) -> None:
    confirmations = _extract_pending_confirmations(task.context)
    if not confirmations:
        return
    lines = [task.dm_notes.strip()] if task.dm_notes else []
    for item in confirmations:
        lines.append(f"[Auto Confirmation] {item['question']} -> {item['default']}")
    task.dm_notes = "\n".join(line for line in lines if line).strip()


def _enqueue_task(state: AgentState, task: TaskExecution) -> None:
    queue = state.get("task_queue", [])
    queue.append(task)
    print(f"\n⬇️  入队任务: {task.description[:50]}...")
    _print_task_payload("Planner 产出的完整 TaskExecution", task)
    state["task_queue"] = queue
    print(f"   队列长度: {len(queue)} 个任务")


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
        confirmations = _extract_pending_confirmations(task.context)
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
            task.dm_notes = result.get("suggestion", "")
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

        return Command(goto="commiter", update=state)

    return executor_node


def create_commiter_node(write_fields_tool):
    """创建固定写回节点。"""

    def commiter_node(state: AgentState) -> Command:
        task = state.get("_current_task")
        result = state.get("_execution_result")

        if not task or not result:
            return Command(goto="planner", update=state)

        print("\n🗂️ Commiter: 开始处理 field_changes")

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
