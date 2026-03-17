"""工作流节点函数 - 最小 planner / task_approval / executor 骨架。"""
from __future__ import annotations

import os
import re

from langchain_core.messages import HumanMessage
from langgraph.graph import END
from langgraph.types import Command, interrupt

from ..types import AgentState, ExecutionResult, PlannedTask
from ..utils.logging import get_logger
from ..utils.script_parser import (
    build_execution_script_state,
    parse_planner_hints,
    render_runtime_markdown,
)

logger = get_logger(__name__)


def _enqueue_task(state: AgentState, task: PlannedTask) -> None:
    queue = state.get("task_queue", [])
    queue.append(task)
    print(f"\n⬇️  入队任务: {task.description[:50]}...")
    state["task_queue"] = queue
    print(f"   队列长度: {len(queue)} 个任务")


def _remove_task_by_id(state: AgentState, task_id: str) -> bool:
    queue = state.get("task_queue", [])
    original_len = len(queue)
    queue = [t for t in queue if t.task_id != task_id]
    state["task_queue"] = queue
    return len(queue) < original_len


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
            context_cache = state.get("_context_cache", {})
            context_cache.pop(current_task.task_id, None)
            state["_context_cache"] = context_cache
            state["_current_task"] = None
            state["_execution_script"] = None
            state["_execution_context"] = None

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
        while queue and queue[0].task_status == "cancelled":
            skipped = queue.pop(0)
            print(f"\n⏭️  跳过已取消任务: {skipped.description[:50]}...")

        state["task_queue"] = queue
        if queue:
            task = queue.pop(0)
            state["task_queue"] = queue
            state["_current_task"] = task
            print(f"\n📋 出队任务: {task.description[:50]}...")
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

        if task.approval_granted:
            return Command(goto="executor", update=state)

        print(f"\n{'=' * 50}")
        print("⏸️  任务审批")
        print(f"{'=' * 50}")
        print(f"任务: {task.description}")
        print(f"类型: {task.task_category}")
        if task.context:
            print(f"\n执行稿预览 (前500字符):\n  {task.context[:500]}...")

        if os.getenv("TRPG_AUTO_CONFIRM") == "1":
            task.approval_granted = True
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
            _remove_task_by_id(state, task.task_id)
            state["_current_task"] = None
            return Command(goto="planner", update=state)
        if action == "modify":
            task.dm_notes = result.get("suggestion", "")
        task.approval_granted = True
        return Command(goto="executor", update=state)

    return task_approval_node


def create_executor_node(executor_agent, store):
    """创建执行节点。"""

    def executor_node(state: AgentState) -> Command:
        task = state.get("_current_task")
        if not task:
            return Command(goto="planner", update=state)

        script_state = state.get("_execution_script")
        context_cache = _ensure_task_cache(state, task.task_id)
        if task.task_category != "world_edit":
            if script_state is None or script_state.task_id != task.task_id:
                script_state = build_execution_script_state(task)
                state["_execution_script"] = script_state
            _refresh_blocked_steps(script_state)

        _update_cache_from_task_context(context_cache, task.context)
        execution_context = _build_execution_context(store, task, script_state, context_cache)
        state["_execution_context"] = execution_context

        print("\n🧱 已构建执行上下文")
        relevant_keys = execution_context.get("relevant_keys", [])
        if relevant_keys:
            print(f"   相关状态键: {', '.join(relevant_keys)}")

        print("\n🎯 Executor: 开始执行任务")
        print(f"   {task.description}")
        print(f"   类型: {task.task_category}")

        result: ExecutionResult = executor_agent.execute(task, execution_context=execution_context)

        if result.field_changes:
            state["changes"] = state.get("changes", []) + result.field_changes
            _invalidate_cache_for_changes(context_cache, result.field_changes)
            print(f"📝 已应用 {len(result.field_changes)} 个状态变更")

        if task.task_category == "world_edit":
            _enqueue_triggered_chains(state, result, task)
            state["_current_task"] = None
            state["_execution_script"] = None
            state["_execution_context"] = None
            return Command(goto="planner", update=state)

        if script_state is None:
            script_state = build_execution_script_state(task)

        previous_active_step_id = script_state.active_step_id
        _apply_step_updates(script_state, result)
        _enqueue_triggered_chains(state, result, task)

        if result.proposed_fragment is not None:
            script_state.history.append(
                f"ignored_fragment:{result.proposed_fragment.anchor_step_id}:{result.proposed_fragment.fragment_summary}"
            )
            logger.info("最小工作流已忽略 proposed_fragment", anchor_step_id=result.proposed_fragment.anchor_step_id)
            result.proposed_fragment = None

        if _is_execution_stalled(previous_active_step_id, script_state, result):
            logger.warning("Executor 停滞，结束当前任务", task_id=task.task_id, active_step_id=previous_active_step_id)
            state["_current_task"] = None
            state["_execution_script"] = None
            state["_execution_context"] = None
            return Command(goto="planner", update=state)

        state["_execution_script"] = script_state
        state["_execution_context"] = None
        if _is_script_complete(script_state):
            print("\n✅ 执行稿完成")
            state["_current_task"] = None
            state["_execution_script"] = None
            return Command(goto="planner", update=state)

        return Command(goto="executor", update=state)

    return executor_node


def _enqueue_triggered_chains(state: AgentState, result: ExecutionResult, task: PlannedTask) -> None:
    if not result.triggered_chains:
        return
    for chain in result.triggered_chains:
        if not isinstance(chain, dict):
            logger.warning("忽略非法 triggered_chain", chain=chain)
            continue
        chain_task = PlannedTask(
            task_id=chain.get("task_id") or f"chain_{task.task_id}_{len(state.get('task_queue', []))}",
            description=chain.get("description", "连锁任务"),
            context=chain.get("description", "连锁任务"),
            actor=chain.get("actor"),
            target=chain.get("target"),
            source="chain",
            task_category="normal",
        )
        _enqueue_task(state, chain_task)


def _apply_step_updates(script_state, result: ExecutionResult) -> None:
    step_map = {step.step_id: step for step in script_state.steps}
    for update in result.step_updates:
        step = step_map.get(update.step_id)
        if step is None:
            continue
        step.status = update.status
        if update.note:
            script_state.history.append(f"{update.step_id}:{update.status}:{update.note}")
    _refresh_blocked_steps(script_state)


def _is_script_complete(script_state) -> bool:
    return all(step.status == "completed" for step in script_state.steps)


def _refresh_blocked_steps(script_state) -> None:
    step_map = {step.step_id: step for step in script_state.steps}
    changed = True
    while changed:
        changed = False
        for step in script_state.steps:
            if step.status != "blocked":
                continue
            if all(step_map.get(dep) is not None and step_map[dep].status == "completed" for dep in step.depends_on):
                step.status = "pending"
                changed = True

    script_state.active_step_id = next(
        (step.step_id for step in script_state.steps if step.status in {"pending", "in_progress"}),
        None,
    )


def _is_execution_stalled(previous_active_step_id: str | None, script_state, result: ExecutionResult) -> bool:
    return (
        previous_active_step_id is not None
        and script_state.active_step_id == previous_active_step_id
        and not result.field_changes
        and not result.step_updates
        and not result.triggered_chains
    )


def _build_execution_context(store, task: PlannedTask, script_state, context_cache: dict[str, object]) -> dict[str, object]:
    relevant_keys: list[str] = []
    state_snapshot: dict[str, str] = {}
    kv_cache = context_cache.setdefault("kv", {})

    for entity in _candidate_entities(task):
        for suffix in ("combat", "spells", "features", "status"):
            key = _resolve_state_key(store, entity, suffix)
            if key and key not in relevant_keys:
                relevant_keys.append(key)
                value = kv_cache.get(key)
                if value is None:
                    value = store.get(key)
                if value is not None:
                    kv_cache[key] = value
                    state_snapshot[key] = value

    active_step = None
    planner_hints: list[dict[str, str]] = []
    script_markdown = task.context
    if script_state is not None:
        script_markdown = render_runtime_markdown(task, script_state)
        active_step = next((step for step in script_state.steps if step.step_id == script_state.active_step_id), None)
        planner_hints = parse_planner_hints(script_markdown)

    return {
        "task_id": task.task_id,
        "task_category": task.task_category,
        "relevant_keys": relevant_keys,
        "state_snapshot": state_snapshot,
        "context_cache": {
            "kv": {key: state_snapshot[key] for key in relevant_keys if key in state_snapshot},
            "rules": dict(context_cache.get("rules", {})),
            "facts": dict(context_cache.get("facts", {})),
        },
        "script_markdown": script_markdown,
        "active_step_id": script_state.active_step_id if script_state is not None else None,
        "active_step": active_step.__dict__ if active_step is not None else None,
        "planner_hints": planner_hints,
        "history": list(script_state.history) if script_state is not None else [],
    }


def _candidate_entities(task: PlannedTask) -> list[str]:
    candidates = [task.actor, task.target]
    entities: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        cleaned = candidate.strip()
        if cleaned not in entities:
            entities.append(cleaned)
        if "(" in cleaned and ")" in cleaned:
            alias = cleaned.split("(", 1)[1].split(")", 1)[0].strip()
            if alias and alias not in entities:
                entities.append(alias)
        base = cleaned.split("(", 1)[0].strip()
        if base and base not in entities:
            entities.append(base)
    return entities


def _resolve_state_key(store, entity: str, suffix: str) -> str | None:
    if not entity:
        return None

    keys = store.get_keys()
    normalized_entity = entity.lower()
    exact = f"{entity}.{suffix}"
    if exact in keys:
        return exact

    for key in keys:
        if not key.endswith(f".{suffix}"):
            continue
        prefix = key.rsplit(".", 1)[0]
        if prefix.lower() == normalized_entity:
            return key
        if normalized_entity in prefix.lower():
            return key
    return None


def _ensure_task_cache(state: AgentState, task_id: str) -> dict[str, object]:
    context_cache = state.get("_context_cache", {})
    task_cache = context_cache.setdefault(task_id, {"kv": {}, "rules": {}, "facts": {}})
    state["_context_cache"] = context_cache
    return task_cache


def _update_cache_from_task_context(task_cache: dict[str, object], markdown: str | None) -> None:
    if not markdown:
        return

    rules_cache = task_cache.setdefault("rules", {})
    kv_cache = task_cache.setdefault("kv", {})
    section_match = re.search(r"## Query Appendix\s*(.*)$", markdown, flags=re.DOTALL)
    if not section_match:
        return

    current_block = None
    for raw_line in section_match.group(1).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[KV"):
            current_block = "kv"
            continue
        if line.startswith("[RAG"):
            current_block = "rag"
            continue
        if not line.startswith("- "):
            continue

        body = line[2:].strip()
        if ":" not in body:
            continue
        key, value = body.split(":", 1)
        key = key.strip()
        value = value.strip()
        if current_block == "kv" and key and value:
            kv_cache.setdefault(key, value)
        elif current_block == "rag" and key and value:
            rules_cache.setdefault(key, value)


def _invalidate_cache_for_changes(task_cache: dict[str, object], changes) -> None:
    kv_cache = task_cache.setdefault("kv", {})
    facts = task_cache.setdefault("facts", {})
    for change in changes:
        key = change.path.rsplit(".", 1)[0] if "." in change.path else change.path
        kv_cache.pop(key, None)
    facts.clear()
