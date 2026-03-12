"""
工作流节点函数 - V7版本 (队列管理 + 事件驱动)

变更:
1. 引入队列管理：入队尾部、插队头部、出队
2. 连锁任务插队头部，优先执行
3. 简化事件处理逻辑
"""
from langchain_core.messages import HumanMessage

from ..types import (
    AgentState, PlannedTask, StateChange,
    TaskCreated, TaskApproved,
    ExecutionCompleted, ChainApproved, ChainRejected
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


def _dequeue_next_task(state: AgentState) -> bool:
    """出队下一个任务

    从队列头部取出任务，设置 _current_task，生成 TaskCreated

    Returns:
        bool: 是否成功出队（队列不为空）
    """
    queue = state.get("task_queue", [])

    if not queue:
        state["_current_task"] = None
        state["_event"] = None
        return False

    # 从头部出队
    next_task = queue.pop(0)
    state["task_queue"] = queue
    state["_current_task"] = next_task
    state["_event"] = TaskCreated(source="planner", task=next_task)

    print(f"\n📋 出队任务: {next_task.description[:50]}...")
    print(f"   队列剩余: {len(queue)} 个任务")

    return True


def _enqueue_task(state: AgentState, task: PlannedTask, priority: bool = False) -> None:
    """入队任务

    Args:
        state: AgentState
        task: 要入队的任务
        priority: 是否插队到头部（连锁任务）
    """
    queue = state.get("task_queue", [])

    if priority:
        # 插队到头部（连锁任务优先）
        queue.insert(0, task)
        print(f"\n⬆️  插队任务: {task.description[:50]}...")
    else:
        # 入队尾部（普通任务）
        queue.append(task)
        print(f"\n⬇️  入队任务: {task.description[:50]}...")

    state["task_queue"] = queue
    print(f"   队列长度: {len(queue)} 个任务")


def _remove_task_from_queue(state: AgentState, task_id: str) -> bool:
    """从队列中移除指定任务

    Returns:
        bool: 是否成功移除
    """
    queue = state.get("task_queue", [])
    original_len = len(queue)

    queue = [t for t in queue if t.task_id != task_id]
    state["task_queue"] = queue

    removed = len(queue) < original_len
    if removed:
        print(f"\n🗑️  从队列移除任务: {task_id}")

    return removed


def create_planner_node(planner_agent):
    """创建PlannerAgent节点 (V7)

    统一任务入口：处理用户输入、连锁任务、任务完成后的队列处理
    """
    def planner_node(state: AgentState) -> AgentState:
        messages = state["messages"]
        current_event = state.get("_event")

        print(f"\n[planner] 进入: event={type(current_event).__name__ if current_event else 'None'}, queue={len(state.get('task_queue', []))}")

        # === 处理事件 ===

        if isinstance(current_event, ChainApproved):
            # 连锁审批通过，生成连锁任务并插队到头部
            chain = current_event
            task_description = f"【连锁:{chain.chain_type}】{chain.description}"
            if chain.source_key:
                task_description += f" [来源:{chain.source_key}]"

            # 生成连锁任务
            task = planner_agent.plan(task_description)
            task.source = "chain"

            # 插队到头部（优先执行）
            _enqueue_task(state, task, priority=True)

            # 立即出队执行（因为是头部）
            _dequeue_next_task(state)

            print(f"🤖 PlannerAgent: 生成连锁任务 - {task.description}")

        elif isinstance(current_event, ChainRejected):
            # 连锁被拒绝，继续出队下一个任务
            print("❌ 连锁已被忽略")
            _dequeue_next_task(state)

        elif isinstance(current_event, ExecutionCompleted):
            # 执行完成，记录变更
            changes = current_event.changes
            if changes:
                state["changes"] = state.get("changes", []) + changes
                print(f"📝 已记录 {len(changes)} 个状态变更到历史")

            # 从队列中移除已完成的任务
            # 注意：当前任务可能已经被dm_confirm_plan在拒绝时移除
            # 这里确保如果还在队列中就移除
            _remove_task_from_queue(state, current_event.task_id)

            # 出队下一个任务
            has_more = _dequeue_next_task(state)
            if not has_more:
                print("✅ 所有任务执行完成")

        elif isinstance(current_event, TaskApproved):
            # TaskApproved 不应该直接到planner，应该在dm_confirm_plan后去executor
            # 这里作为容错处理
            print("⚠️  收到意外的 TaskApproved 事件")
            state["_event"] = None

        else:
            # === 处理新输入 ===
            last_message = messages[-1] if messages else None

            if isinstance(last_message, HumanMessage):
                user_input = last_message.content

                # 跳过已处理的消息标记
                if user_input.startswith("【已处理:"):
                    print(f"⏭️  跳过已处理的消息")
                    # 尝试出队下一个任务
                    _dequeue_next_task(state)
                    return state

                # 区分显示来源
                if user_input.startswith("【连锁:"):
                    print(f"\n🎮 连锁任务输入: {user_input}")
                else:
                    print(f"\n🎮 DM: {user_input}")

                # 生成任务
                task = planner_agent.plan(user_input)

                # 入队尾部
                _enqueue_task(state, task, priority=False)

                # 尝试出队（如果队列中只有这一个任务，就立即执行）
                _dequeue_next_task(state)

                print(f"🤖 PlannerAgent: 生成任务 - {task.description}")
                print(f"   行动者: {task.actor}, 目标: {task.target}")

            else:
                # 没有新输入，尝试出队
                _dequeue_next_task(state)

        return state
    return planner_node


def dm_confirm_plan_node(state: AgentState, auto_confirm: bool = False) -> AgentState:
    """DM任务审批节点 (V7)

    读取 _current_task，生成 TaskApproved 事件
    如果拒绝，从队列中移除任务并出队下一个
    """
    task = state.get("_current_task")
    if not task:
        print("\n⚠️  没有当前任务需要审批")
        state["_event"] = None
        return state

    print(f"\n" + "="*50)
    print(f"⏸️  DM 任务审批节点")
    print(f"="*50)
    print(f"任务: {task.description}")
    print(f"行动者: {task.actor}")
    print(f"目标: {task.target}")
    if task.context:
        print(f"\n执行上下文 (前500字符):")
        print(f"  {task.context[:500]}...")

    # 检查是否自动确认（测试模式）
    import os
    if os.getenv("TRPG_AUTO_CONFIRM") == "1":
        print("\n🤖 [自动确认模式] 已自动批准")
        state["_event"] = TaskApproved(source="dm_confirm_plan", task=task, dm_notes=None)
        return state

    # 手动确认
    print("\n💡 提示: 输入 y 确认，n 拒绝，或直接输入修改建议")
    while True:
        response = input("> ").strip()
        lower = response.lower()

        if lower in ('y', 'yes'):
            print("✅ 已确认执行")
            state["_event"] = TaskApproved(source="dm_confirm_plan", task=task, dm_notes=None)
            break
        elif lower in ('n', 'no'):
            print("❌ 已拒绝执行")
            # 从队列中移除该任务
            _remove_task_from_queue(state, task.task_id)
            # 出队下一个任务
            has_more = _dequeue_next_task(state)
            if not has_more:
                print("✅ 所有任务处理完成")
            break
        elif response:  # 其他输入视为修改建议
            task.dm_notes = response
            print(f"✅ 已采纳修改建议并确认执行")
            print(f"   DM批注: {response[:80]}...")
            state["_event"] = TaskApproved(source="dm_confirm_plan", task=task, dm_notes=response)
            break
        else:
            print("请输入 y(确认)、n(拒绝) 或修改建议")

    return state


def create_executor_node(executor_agent):
    """创建ExecutorAgent节点 (V7)

    读取 _current_task，生成 ExecutionCompleted 事件
    """
    def executor_node(state: AgentState) -> AgentState:
        task = state.get("_current_task")
        if not task:
            print("\n⚠️  没有当前任务需要执行")
            state["_event"] = None
            return state

        print(f"\n🎯 Executor: 开始执行任务")
        print(f"   {task.description}")

        # DEBUG: 输出 Planner -> Executor 的完整原始内容
        logger.debug(
            f"Planner -> Executor 完整任务内容:\n"
            f"{task.context}"
        )

        # 调用ExecutorAgent执行任务
        from ..types import ExecutionResult
        result: ExecutionResult = executor_agent.execute(task)

        # 将 ExecutionResult 转换为 StateChange 列表
        changes = result.field_changes if result.field_changes else []

        # 生成 ExecutionCompleted 事件
        state["_event"] = ExecutionCompleted(
            source="executor",
            task_id=result.task_id,
            success=result.success,
            narration=result.narration,
            changes=changes,
            triggered_chains=result.triggered_chains
        )

        print(f"\n✅ Executor: 执行完成")
        print(f"   {result.narration}")
        if changes:
            print(f"   生成 {len(changes)} 个状态变更")
        if result.triggered_chains:
            print(f"   检测到 {len(result.triggered_chains)} 个连锁触发")

        return state
    return executor_node


def create_chain_confirm_node():
    """创建连锁审批节点 (V7)

    读取 _event (ExecutionCompleted)，生成 ChainApproved 或 ChainRejected 事件
    """
    def chain_confirm_node(state: AgentState) -> AgentState:
        event = state.get("_event")

        if not isinstance(event, ExecutionCompleted):
            print("\n⚠️  没有执行结果需要处理连锁")
            state["_event"] = None
            return state

        triggered = event.triggered_chains
        if not triggered:
            # 没有连锁，直接结束
            state["_event"] = None
            return state

        chain = triggered[0]  # 处理第一个连锁

        print(f"\n" + "="*50)
        print(f"⏸️  DM 连锁审批节点")
        print(f"="*50)
        print(f"连锁类型: {chain.get('type', 'unknown')}")
        print(f"描述: {chain.get('description', '')}")

        # 检查是否自动确认（测试模式）
        import os
        if os.getenv("TRPG_AUTO_CONFIRM") == "1":
            print("\n🤖 [自动确认模式] 已自动批准连锁")
            state["_event"] = ChainApproved(
                source="dm_confirm_chain",
                chain_type=chain.get('type', 'unknown'),
                description=chain.get('description', ''),
                source_key=chain.get('source_key', '')
            )
            return state

        print("\n💡 提示: 输入 y 确认触发，n 忽略")
        while True:
            response = input("> ").strip().lower()
            if response in ('y', 'yes'):
                print("✅ 已确认触发连锁")

                # 生成 ChainApproved 事件
                state["_event"] = ChainApproved(
                    source="dm_confirm_chain",
                    chain_type=chain.get('type', 'unknown'),
                    description=chain.get('description', ''),
                    source_key=chain.get('source_key', '')
                )

                break
            elif response in ('n', 'no'):
                print("❌ 已忽略连锁")
                state["_event"] = ChainRejected(source="dm_confirm_chain", chain_type=chain.get('type', 'unknown'))
                break
            else:
                print("请输入 y(确认) 或 n(忽略)")

        return state
    return chain_confirm_node


# ============== 路由函数 (基于事件类型) ==============

def route_after_planner(state: AgentState) -> str:
    """planner节点后的路由

    基于 _event 类型决定下一步
    """
    event = state.get("_event")

    if isinstance(event, TaskCreated):
        return "dm_confirm_plan"
    else:
        # 没有任务创建，结束
        return "end"


def route_after_plan_confirm(state: AgentState) -> str:
    """dm_confirm_plan节点后的路由"""
    event = state.get("_event")

    if isinstance(event, TaskApproved):
        return "executor"
    else:
        # 其他情况（如拒绝后已出队下一个，_event 为 None 或有新的 TaskCreated）
        # 回到planner继续处理
        return "planner"


def route_after_executor(state: AgentState) -> str:
    """executor节点后的路由"""
    event = state.get("_event")

    if isinstance(event, ExecutionCompleted):
        if event.triggered_chains:
            return "dm_confirm_chain"
        else:
            # 无连锁，回到planner出队下一个
            return "planner"
    else:
        return "planner"


def route_after_chain_confirm(state: AgentState) -> str:
    """dm_confirm_chain节点后的路由"""
    # 无论 ChainApproved 还是 ChainRejected，都回到planner处理
    return "planner"
