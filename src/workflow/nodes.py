"""工作流节点函数 - 扁平化队列架构。"""
import uuid
import os

from langchain_core.messages import HumanMessage
from langgraph.types import Command, interrupt
from langgraph.graph import END

from ..types import AgentState, PlannedTask, StateChange, ExecutionResult, DecisionPoint, ExecutionState, DecisionTiming
from ..utils.logging import get_logger

logger = get_logger(__name__)


# ============== 队列操作辅助函数 ==============

def _enqueue_task(state: AgentState, task: PlannedTask, priority: bool = False) -> None:
    """入队任务

    Args:
        state: AgentState
        task: 要入队的任务
        priority: 是否插队到头部（响应/连锁任务）
    """
    queue = state.get("task_queue", [])

    if priority:
        queue.insert(0, task)
        print(f"\n⬆️  插队任务: {task.description[:50]}...")
    else:
        queue.append(task)
        print(f"\n⬇️  入队任务: {task.description[:50]}...")

    state["task_queue"] = queue
    print(f"   队列长度: {len(queue)} 个任务")


def _remove_task_by_id(state: AgentState, task_id: str) -> bool:
    """从队列中移除指定任务"""
    queue = state.get("task_queue", [])
    original_len = len(queue)

    queue = [t for t in queue if t.task_id != task_id]
    state["task_queue"] = queue

    return len(queue) < original_len


def _update_task_status(state: AgentState, task_id: str, new_status: str) -> bool:
    """更新任务状态"""
    queue = state.get("task_queue", [])
    for task in queue:
        if task.task_id == task_id:
            task.task_status = new_status
            print(f"   更新任务 {task_id[:8]}... 状态为: {new_status}")
            return True
    return False


def _find_task_by_id(state: AgentState, task_id: str) -> PlannedTask | None:
    """在队列中查找任务。"""
    for task in state.get("task_queue", []):
        if task.task_id == task_id:
            return task
    return None


# ============== Planner 节点 ==============

def create_planner_node(planner_agent):
    """创建规划节点 (V10)

    返回 Command 直接控制流程:
    - 有新任务: goto="dm_decision"
    - 无任务: goto=END
    """
    def planner_node(state: AgentState) -> Command:
        messages = state["messages"]
        current_task = state.get("_current_task")
        queue = state.get("task_queue", [])
        planned_message_count = state.get("_planned_message_count", 0)

        print(f"\n[planner] 进入: queue={len(queue)}")

        # 情况1: 当前有任务执行完成，清除它
        if current_task is not None:
            print(f"   当前任务完成: {current_task.description[:40]}...")
            state["_current_task"] = None

        # 情况2: 处理新用户输入（最后一条是人类消息且未处理）
        # 注意：只有当队列为空且没有当前任务时才处理，避免循环回来重复处理。
        # messages 使用 add_messages reducer，不能依赖“删除 HumanMessage”来防重。
        last_message = messages[-1] if messages else None
        if (
            isinstance(last_message, HumanMessage)
            and not queue
            and not current_task
            and len(messages) > planned_message_count
        ):
            user_input = last_message.content
            # 新输入，生成任务
            print(f"\n🎮 DM: {user_input}")
            tasks = planner_agent.plan(user_input)

            for task in tasks:
                _enqueue_task(state, task, priority=False)

            state["_planned_message_count"] = len(messages)

        # 情况3: 出队下一个任务
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
            print(f"   队列剩余: {len(queue)} 个任务")
            print(f"🤖 Planner: 准备执行 - {task.description}")

            # 使用 Command 直接跳转到 dm_decision
            return Command(goto="dm_decision", update=state)
        else:
            print("✅ 所有任务执行完成")
            # 使用 Command 直接结束
            return Command(goto=END, update=state)

    return planner_node


# ============== DM 决策节点 ==============

def create_dm_decision_node():
    """创建DM决策节点 (V11)

    使用 interrupt 替代 input() 阻塞调用:
    - 询问确认/拒绝/修改

    返回 Command 控制流程:
    - 批准/有任务: goto="context_builder"
    - 拒绝/无任务: goto="planner"
    """
    def dm_decision_node(state: AgentState) -> Command:
        task = state.get("_current_task")
        if not task:
            print("\n⚠️  没有当前任务")
            return Command(goto="planner", update=state)

        if task.approval_granted:
            print("\n✅ 跳过重复审批，继续恢复执行")
            return Command(goto="context_builder", update=state)

        return _handle_task_approval(state, task)

    return dm_decision_node


def _handle_task_approval(state: AgentState, task: PlannedTask) -> Command:
    """处理普通任务审批 - 使用 interrupt"""
    print(f"\n" + "="*50)
    print(f"⏸️  DM 任务审批")
    print(f"="*50)
    print(f"任务: {task.description}")
    print(f"类型: {task.task_category}")
    if task.actor:
        print(f"行动者: {task.actor}")
    if task.target:
        print(f"目标: {task.target}")

    if task.context:
        print(f"\n执行上下文 (前500字符):")
        print(f"  {task.context[:500]}...")

    # 自动确认模式（测试用）
    if os.getenv("TRPG_AUTO_CONFIRM") == "1":
        print("\n🤖 [自动确认模式] 已自动批准")
        task.approval_granted = True
        return Command(goto="context_builder", update=state)

    # 使用 interrupt 暂停执行，等待外部输入
    result = interrupt({
        "type": "task_approval",
        "task": {
            "task_id": task.task_id,
            "description": task.description,
            "task_category": task.task_category,
            "actor": task.actor,
            "target": task.target,
            "context_preview": task.context[:500] if task.context else "",
        },
        "options": ["approve", "reject", "modify"]
    })

    # 恢复后处理结果
    action = result.get("action", "approve")

    if action == "reject":
        print("❌ 已拒绝执行")
        # 从队列中移除该任务
        _remove_task_by_id(state, task.task_id)
        # 清除当前任务
        state["_current_task"] = None
        # 如果有关联任务，标记为可执行
        if task.related_task_id:
            _update_task_status(state, task.related_task_id, "pending")
        return Command(goto="planner", update=state)

    elif action == "modify":
        suggestion = result.get("suggestion", "")
        task.dm_notes = suggestion
        task.approval_granted = True
        print(f"✅ 已采纳修改建议: {suggestion[:80]}...")
        return Command(goto="context_builder", update=state)

    else:  # approve
        task.approval_granted = True
        print("✅ 已确认执行")
        return Command(goto="context_builder", update=state)


def create_decision_point_node():
    """创建决策点检查节点

    扁平化版本：
    - 主任务在执行前检查一次决策窗口
    - 选择响应后，将响应任务插队到队列头部
    - 原任务重新入队，等待响应任务执行完毕后继续
    - 如果响应任务自身带有嵌套决策点，也会先进入决策窗口
    - world_edit 任务跳过决策点检查
    """
    def decision_point_node(state: AgentState) -> Command:
        task = state.get("_current_task")
        if not task:
            print("\n⚠️  没有当前任务需要检查决策点")
            return Command(goto="planner", update=state)

        if task.task_category == "world_edit":
            return Command(goto="executor", update=state)

        execution_state = state.get("_execution_state")
        current_timing = None
        if execution_state and execution_state.task_id == task.task_id and execution_state.phase_index < len(execution_state.phases):
            current_timing = execution_state.phases[execution_state.phase_index]

        all_points = execution_state.decision_points if execution_state else (task.decision_points or [])

        if execution_state and current_timing:
            candidate_points = [
                point for point in execution_state.decision_points
                if point.timing == current_timing
            ]
        else:
            candidate_points = task.decision_points or []

        available_option_names = [
            point.option_name
            for point in all_points
            if point.option_name
        ]
        decision_points = [
            point for point in candidate_points
            if not _is_nested_decision_point(point, available_option_names)
        ]

        if not decision_points:
            goto = "executor" if task.task_category == "decision_response" else "resolution_runner"
            return Command(goto=goto, update=state)

        print(f"\n" + "=" * 50)
        print("⚡ 决策窗口")
        print("=" * 50)
        print(f"当前任务: {task.description}")
        print("可用响应:")
        for i, point in enumerate(decision_points, 1):
            option_name = point.option_name or "默认响应"
            print(f"   {i}. {point.decider} [{point.timing}] {option_name}: {point.description}")
        print("   n. 不触发任何响应")

        if os.getenv("TRPG_AUTO_CONFIRM") == "1":
            choice = "1"
            print("🤖 [自动确认模式] 自动选择第一个响应")
        else:
            result = interrupt({
                "type": "decision_point_choice",
                "task": {
                    "task_id": task.task_id,
                    "description": task.description,
                    "actor": task.actor,
                    "target": task.target,
                },
                "decision_points": [
                    {
                        "decider": point.decider,
                        "timing": point.timing,
                        "option_name": point.option_name,
                        "description": point.description,
                        "condition": point.condition,
                        "metadata": point.metadata,
                    }
                    for point in decision_points
                ],
                "options": [str(i) for i in range(1, len(decision_points) + 1)] + ["n"],
            })
            choice = result.get("choice", "n")

        if choice == "n" or not choice.isdigit():
            print("❌ 不触发任何响应")
            goto = "executor" if task.task_category == "decision_response" else "resolution_runner"
            return Command(goto=goto, update=state)

        idx = int(choice) - 1
        if not 0 <= idx < len(decision_points):
            print("⚠️  选择无效，继续执行原任务")
            goto = "executor" if task.task_category == "decision_response" else "resolution_runner"
            return Command(goto=goto, update=state)

        selected_point = decision_points[idx]
        nested_points = _extract_nested_decision_points(all_points, selected_point)
        response_task = _create_decision_response_task(selected_point, task, nested_points)
        if execution_state and current_timing:
            # 当前最小实现只支持每个 timing 选择一个响应。
            # 一旦选择了响应，就移除该 timing 的决策点，避免回到主任务后重复打开同一窗口。
            execution_state.decision_points = [
                point for point in execution_state.decision_points
                if point.timing != current_timing
            ]
            state["_execution_state"] = execution_state
        else:
            task.decision_points = [
                point for point in task.decision_points
                if point is not selected_point
            ]
        _enqueue_task(state, task, priority=True)
        _enqueue_task(state, response_task, priority=True)
        state["_current_task"] = None

        print(f"✅ 已插入响应任务: {response_task.description}")
        return Command(goto="planner", update=state)

    return decision_point_node

def create_context_builder_node(store):
    """创建执行上下文构建节点。

    由工作流统一读取 KV，并向 executor 注入最小必要状态快照。
    """
    def context_builder_node(state: AgentState) -> Command:
        task = state.get("_current_task")
        if not task:
            return Command(goto="planner", update=state)

        execution_context = _build_execution_context(store, task)
        state["_execution_context"] = execution_context

        print("\n🧱 已构建执行上下文")
        relevant_keys = execution_context.get("relevant_keys", [])
        if relevant_keys:
            print(f"   相关状态键: {', '.join(relevant_keys)}")

        if task.task_category == "world_edit":
            return Command(goto="executor", update=state)
        if task.task_category == "decision_response" and task.decision_points:
            return Command(goto="decision_point_check", update=state)
        if task.task_category == "decision_response":
            return Command(goto="executor", update=state)
        return Command(goto="resolution_builder", update=state)

    return context_builder_node


def create_resolution_builder_node(executor_agent):
    """创建结算计划构建节点。"""
    def resolution_builder_node(state: AgentState) -> Command:
        task = state.get("_current_task")
        if not task:
            print("\n⚠️  没有当前任务需要构建结算计划")
            return Command(goto="planner", update=state)

        if task.task_category in ("decision_response", "world_edit"):
            return Command(goto="executor", update=state)

        existing = state.get("_execution_state")
        if existing and existing.task_id == task.task_id:
            next_phase = existing.phases[existing.phase_index] if existing.phase_index < len(existing.phases) else "done"
            goto = "decision_point_check" if next_phase != "apply_consequence" else "resolution_runner"
            return Command(goto=goto, update=state)

        print(f"\n🧭 构建结算计划: {task.description}")
        execution_context = state.get("_execution_context") or {}
        result: ExecutionResult = executor_agent.execute(task, execution_context=execution_context)

        phases: list[str] = []
        result_decision_points = result.decision_points or task.decision_points or []
        timings = {point.timing for point in result_decision_points}
        for timing in (
            DecisionTiming.BEFORE_ACTION.value,
            DecisionTiming.BEFORE_RESOLUTION.value,
            DecisionTiming.BEFORE_CONSEQUENCE.value,
        ):
            if timing in timings:
                phases.append(timing)

        if result.consequence_changes:
            phases.append("apply_consequence")

        if result.triggered_chains or result.execution_context.get("after_changes"):
            phases.append(DecisionTiming.AFTER_ACTION.value)

        if not phases:
            phases = ["apply_consequence"]

        state["_execution_state"] = ExecutionState(
            task_id=task.task_id,
            phase_index=0,
            phases=phases,
            narration=result.narration,
            direct_changes=result.field_changes,
            consequence_changes=result.consequence_changes,
            after_changes=result.execution_context.get("after_changes", []),
            decision_points=result_decision_points,
            triggered_chains=result.triggered_chains,
            resolution_effects=[],
            execution_context=execution_context,
        )

        if result.field_changes:
            state["changes"] = state.get("changes", []) + result.field_changes
            print(f"📝 已应用 {len(result.field_changes)} 个立即状态变更")

        first_phase = phases[0]
        goto = "decision_point_check" if first_phase != "apply_consequence" else "resolution_runner"
        return Command(goto=goto, update=state)

    return resolution_builder_node


def create_resolution_runner_node():
    """创建阶段化结算推进节点。"""
    def resolution_runner_node(state: AgentState) -> Command:
        task = state.get("_current_task")
        execution_state = state.get("_execution_state")
        if not task or not execution_state or execution_state.task_id != task.task_id:
            return Command(goto="executor", update=state)

        if execution_state.phase_index >= len(execution_state.phases):
            state["_execution_state"] = None
            state["_current_task"] = None
            return Command(goto="planner", update=state)

        phase = execution_state.phases[execution_state.phase_index]
        print(f"\n⏭️  推进结算阶段: {phase}")

        if phase == "apply_consequence":
            changes = _apply_resolution_effects(
                execution_state.consequence_changes,
                execution_state.resolution_effects,
            )
            if changes:
                state["changes"] = state.get("changes", []) + changes
                print(f"📝 已应用 {len(changes)} 个结果阶段变更")

        elif phase == DecisionTiming.AFTER_ACTION.value:
            after_changes = _apply_resolution_effects(
                execution_state.after_changes,
                execution_state.resolution_effects,
            )
            if after_changes:
                state["changes"] = state.get("changes", []) + after_changes
                print(f"📝 已应用 {len(after_changes)} 个收尾阶段变更")

            if execution_state.triggered_chains:
                for chain in execution_state.triggered_chains:
                    chain_task = _create_chain_task(chain, task.task_id)
                    _enqueue_task(state, chain_task, priority=True)
                print(f"   已生成 {len(execution_state.triggered_chains)} 个连锁任务")

        execution_state.phase_index += 1
        state["_execution_state"] = execution_state

        if execution_state.phase_index >= len(execution_state.phases):
            print(f"\n✅ 结算完成")
            print(f"   {execution_state.narration}")
            state["_execution_state"] = None
            state["_current_task"] = None
            return Command(goto="planner", update=state)

        next_phase = execution_state.phases[execution_state.phase_index]
        goto = "decision_point_check" if next_phase != "apply_consequence" else "resolution_runner"
        return Command(goto=goto, update=state)

    return resolution_runner_node


# ============== Executor 节点 ==============

def create_executor_node(executor_agent):
    """创建ExecutorAgent节点 (V10)

    返回 Command 控制流程:
    - 总是回到 planner 出队下一个任务
    """
    def executor_node(state: AgentState) -> Command:
        task = state.get("_current_task")
        if not task:
            print("\n⚠️  没有当前任务需要执行")
            return Command(goto="planner", update=state)

        print(f"\n🎯 Executor: 开始执行任务")
        print(f"   {task.description}")
        print(f"   类型: {task.task_category}")

        # 调用ExecutorAgent执行任务
        execution_context = state.get("_execution_context") or {}
        result: ExecutionResult = executor_agent.execute(task, execution_context=execution_context)

        # 应用状态变更
        if result.field_changes:
            state["changes"] = state.get("changes", []) + result.field_changes
            print(f"📝 已应用 {len(result.field_changes)} 个状态变更")
            for c in result.field_changes:
                print(f"   [{c.operation.value}] {c.path}: {c.old_value} -> {c.new_value}")

        # 响应任务会立即应用自己的直接变更，并把对主任务的修正写回执行状态。
        triggered_chains = result.triggered_chains if result.triggered_chains else []
        if task.task_category == "decision_response":
            if triggered_chains:
                print(f"   已过滤响应任务的 {len(triggered_chains)} 个连锁触发")
            triggered_chains = []

            handled_related_response = False
            if result.resolution_effects and task.related_task_id:
                related_task = _find_task_by_id(state, task.related_task_id)
                if related_task and related_task.task_category == "decision_response":
                    if any(effect.get("effect_type") == "negate_consequence" for effect in result.resolution_effects):
                        _remove_task_by_id(state, task.related_task_id)
                        handled_related_response = True
                        print("   已否定并移除被打断的响应任务")

            if result.resolution_effects and not handled_related_response and state.get("_execution_state") is not None:
                execution_state = state["_execution_state"]
                execution_state.resolution_effects.extend(result.resolution_effects)
                if any(effect.get("effect_type") == "negate_consequence" for effect in result.resolution_effects):
                    # 硬保护：一旦响应明确否定主任务结果，直接清空待落地结果，
                    # 避免后续阶段因 LLM 叙述漂移或 effect 丢失而继续扣血/生效。
                    execution_state.consequence_changes = []
                    execution_state.after_changes = []
                    print("   已清空主任务待结算结果，确保 negate_consequence 生效")
                state["_execution_state"] = execution_state
                print(f"   已记录 {len(result.resolution_effects)} 个结算修正效果")

            if task.related_task_id and not handled_related_response:
                _update_task_status(state, task.related_task_id, "pending")
                print(f"   响应任务完成，关联任务已标记为可执行")

        # 如果有连锁，直接生成连锁任务入队
        if triggered_chains:
            for chain in triggered_chains:
                chain_task = _create_chain_task(chain, task.task_id)
                _enqueue_task(state, chain_task, priority=True)
            print(f"   已生成 {len(triggered_chains)} 个连锁任务")

        print(f"\n✅ Executor: 执行完成")
        print(f"   {result.narration}")

        # 任务完成，清除当前任务
        state["_current_task"] = None

        # 使用 Command 回到 planner
        state["_execution_context"] = None
        return Command(goto="planner", update=state)

    return executor_node


def _create_decision_response_task(
    point: DecisionPoint,
    source_task: PlannedTask,
    nested_points: list[DecisionPoint] | None = None,
) -> PlannedTask:
    """根据决策点创建插队响应任务"""
    option_name = point.option_name or "默认响应"
    return PlannedTask(
        task_id=f"response_{uuid.uuid4().hex[:8]}",
        description=f"【响应】{point.decider} 执行 {option_name}",
        context=f"""决策点响应动作
来源任务: {source_task.task_id}
原任务: {source_task.description}
触发时机: {point.timing}
触发条件: {point.condition}
决策者: {point.decider}
响应动作: {option_name}
说明: {point.description}
附加元数据: {point.metadata}
""",
        actor=point.decider,
        target=source_task.actor,
        source="chain",
        task_category="decision_response",
        task_status="pending",
        related_task_id=source_task.task_id,
        decision_points=nested_points or []
    )


def _create_chain_task(chain: dict, source_task_id: str) -> PlannedTask:
    """根据连锁信息创建任务"""
    chain_type = chain.get("type", "unknown")
    description = chain.get("description", f"【连锁:{chain_type}】")
    actor = chain.get("actor", "未知")

    return PlannedTask(
        task_id=f"chain_{uuid.uuid4().hex[:8]}",
        description=description,
        context=f"""连锁任务
类型: {chain_type}
描述: {description}
来源任务: {source_task_id}

连锁信息:
{chain}
""",
        actor=actor,
        target=None,
        source="chain",
        task_category="normal",
        task_status="pending",
        decision_points=[]
    )


def _apply_resolution_effects(
    base_changes: list[StateChange],
    resolution_effects: list[dict],
) -> list[StateChange]:
    """将响应任务产生的修正效果应用到待结算变更。

    当前最小实现只支持一种效果：
    - negate_consequence: 否定当前结果阶段的全部变更
    """
    if not base_changes:
        return []

    changes = list(base_changes)
    for effect in resolution_effects:
        effect_type = effect.get("effect_type", "")
        if effect_type == "negate_consequence":
            return []
    return changes


def _build_execution_context(store, task: PlannedTask) -> dict[str, object]:
    relevant_keys: list[str] = []
    state_snapshot: dict[str, str] = {}

    for entity in _candidate_entities(task):
        for suffix in ("combat", "spells", "features", "status"):
            key = _resolve_state_key(store, entity, suffix)
            if key and key not in relevant_keys:
                relevant_keys.append(key)
                value = store.get(key)
                if value is not None:
                    state_snapshot[key] = value

    context = {
        "task_id": task.task_id,
        "task_category": task.task_category,
        "relevant_keys": relevant_keys,
        "state_snapshot": state_snapshot,
    }

    if task.task_category == "decision_response":
        context["response_window"] = {
            "source_task_id": task.related_task_id,
            "description": task.description,
        }

    return context


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


def _is_nested_decision_point(point: DecisionPoint, option_names: list[str]) -> bool:
    """判断某个决策点是否依赖于另一个响应动作先发生。"""
    if not option_names:
        return False

    haystacks = [point.condition or "", point.description or ""]
    for option_name in option_names:
        if not option_name:
            continue
        for haystack in haystacks:
            if option_name in haystack and point.option_name != option_name:
                return True
    return False


def _extract_nested_decision_points(
    candidate_points: list[DecisionPoint],
    selected_point: DecisionPoint,
) -> list[DecisionPoint]:
    """提取依赖于当前已选响应的嵌套决策点。"""
    option_name = selected_point.option_name or ""
    if not option_name:
        return []

    nested_points: list[DecisionPoint] = []
    for point in candidate_points:
        if point is selected_point:
            continue
        haystack = f"{point.condition} {point.description}"
        if option_name in haystack:
            nested_points.append(point)
    return nested_points
