"""
工作流节点函数 - V3版本
"""
from langchain_core.messages import HumanMessage

from ..types import AgentState, ChainTrigger, PlannedTask, StateChange


def create_planner_node(planner_agent):
    """创建PlannerAgent节点"""
    def planner_node(state: AgentState) -> AgentState:
        messages = state["messages"]
        last_message = messages[-1] if messages else None

        if isinstance(last_message, HumanMessage):
            user_input = last_message.content
            print(f"\n🎮 DM: {user_input}")

            # 调用PlannerAgent生成任务
            task = planner_agent.plan(user_input)

            print(f"🤖 PlannerAgent: 生成任务 - {task.description}")
            print(f"   行动者: {task.actor}, 目标: {task.target}, 动作: {task.action}")

            state["current_task"] = task
            state["task_queue"] = state.get("task_queue", []) + [task]

        return state
    return planner_node


def dm_confirm_plan_node(state: AgentState) -> AgentState:
    """DM任务审批节点"""
    task = state.get("current_task")
    if not task:
        return state

    print(f"\n" + "="*50)
    print(f"⏸️  DM 任务审批节点")
    print(f"="*50)
    print(f"任务: {task.description}")
    print(f"行动者: {task.actor}")
    print(f"目标: {task.target}")
    print(f"动作: {task.action}")
    if task.context:
        print(f"\n执行上下文:")
        for k, v in task.context.items():
            print(f"  {k}: {v}")

    print(f"\n✅ 自动确认执行")
    state["plan_approval_result"] = True

    return state


def create_executor_node(executor_agent):
    """创建ExecutorAgent节点"""
    def executor_node(state: AgentState) -> AgentState:
        task = state.get("current_task")
        if not task:
            return state

        # 调用ExecutorAgent执行任务
        result = executor_agent.execute(task)

        # 记录执行结果
        state["execution_result"] = result

        # 将变更转换为pending_changes格式
        pending = []
        for change in result.changes:
            pending.append({
                "op": change.operation.upper(),
                "key": change.path,
                "value": change.new_value
            })
        state["pending_changes"] = pending

        # 记录committed_changes
        state["committed_changes"] = state.get("committed_changes", []) + result.changes

        return state
    return executor_node


def create_chainagent_node(chain_agent):
    """创建ChainAgent节点 (V3版本)"""
    def chainagent_node(state: AgentState) -> AgentState:
        changes = state.get("committed_changes", [])
        if not changes:
            return state

        # 调用V3 check_chains
        triggers, pending_tasks = chain_agent.check_chains(changes[-5:], "")

        state["chain_triggers"] = triggers
        state["pending_chain_tasks"] = pending_tasks

        if triggers:
            print(f"\n🔗 ChainAgent: 检测到 {len(triggers)} 个连锁触发")
            for t in triggers:
                print(f"   [{t.priority}] {t.condition}")
        else:
            print(f"\n🔗 ChainAgent: 无连锁反应")

        return state
    return chainagent_node


def dm_confirm_chain_node(state: AgentState) -> AgentState:
    """DM连锁审批节点"""
    pending_tasks = state.get("pending_chain_tasks", [])
    if not pending_tasks:
        return state

    print(f"\n" + "="*50)
    print(f"⏸️  DM 连锁审批节点")
    print(f"="*50)

    for i, task in enumerate(pending_tasks, 1):
        print(f"\n[{i}] {task.description}")
        print(f"    行动者: {task.actor}")
        print(f"    目标: {task.target}")
        print(f"    动作: {task.action}")

    print(f"\n✅ 自动确认连锁")
    state["chain_approval_result"] = True

    # 将确认的任务加入队列
    for task in pending_tasks:
        state["task_queue"] = state.get("task_queue", []) + [task]

    return state


def next_task_node(state: AgentState) -> AgentState:
    """处理下一个任务"""
    queue = state.get("task_queue", [])
    current = state.get("current_task")

    if current and current in queue:
        queue.remove(current)

    if queue:
        state["current_task"] = queue[0]
        # 重置相关状态
        state["execution_result"] = None
        state["pending_changes"] = []
        state["chain_triggers"] = []
        state["pending_chain_tasks"] = []
        print(f"\n{'='*50}")
        print(f"📝 新任务: {queue[0].description}")
    else:
        state["current_task"] = None

    state["task_queue"] = queue
    return state


def should_continue_chain(state: AgentState):
    """决定连锁后下一步"""
    if state.get("pending_chain_tasks"):
        return "dm_confirm_chain"
    return "next_task"


def should_continue_next_task(state: AgentState):
    """决定是否继续下一个任务"""
    if state.get("current_task"):
        return "executor"
    return "end"
