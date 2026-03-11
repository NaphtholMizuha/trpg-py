"""
工作流节点函数 - V4版本 (简化架构)

变更:
1. 删除 ChainAgent 相关节点 (create_chainagent_node, dm_confirm_chain_node)
2. 添加 Writer 节点包装函数
3. 更新条件边函数 (has_triggered_chains 替代 should_run_chain_agent)
4. 更新 next_task_node 支持循环返回 Planner
"""
from langchain_core.messages import HumanMessage

from ..types import AgentState, PlannedTask, StateChange, ExecutionResult
from ..utils.logging import get_logger

logger = get_logger(__name__)


def create_planner_node(planner_agent):
    """创建PlannerAgent节点

    统一任务入口：处理用户输入和连锁任务
    队列是"待执行"存储区，取任务时立即出队
    """
    def planner_node(state: AgentState) -> AgentState:
        messages = state["messages"]
        last_message = messages[-1] if messages else None
        queue = state.get("task_queue", [])
        current = state.get("current_task")
        approval = state.get("plan_approval_result")

        # 如果已有当前任务且已审批，需要判断是刚从dm_confirm回来还是executor执行完回来
        # 通过检查execution_result来判断：如果有结果，说明executor已执行完
        execution_result = state.get("execution_result")
        
        if current and approval is True and execution_result is None:
            # 刚从dm_confirm回来，去executor执行
            return state
        
        if current and approval is True and execution_result is not None:
            # executor已执行完，清空当前任务，继续出队下一个
            state["current_task"] = None
            state["plan_approval_result"] = None
            state["execution_result"] = None
            # 继续下面的出队逻辑

        # 如果当前任务被拒绝，清空它，继续出队下一个
        if current and approval is False:
            state["current_task"] = None
            state["plan_approval_result"] = None
            # 继续下面的出队逻辑

        # 检查是否有连锁任务需要处理（从executor回来）
        execution_result = state.get("execution_result")
        triggered_chains = execution_result.triggered_chains if execution_result else []

        if triggered_chains:
            # 有连锁触发，生成连锁任务并入队
            logger.info("检测到连锁触发，生成连锁任务", chains=triggered_chains)
            print(f"\n🔗 检测到 {len(triggered_chains)} 个连锁触发")

            for chain in triggered_chains:
                print(f"   - {chain.get('type', 'unknown')}: {chain.get('description', '')}")

            # 创建连锁任务并入队
            for chain in triggered_chains:
                task = planner_agent.plan_chain_task(chain, state)
                if task:
                    queue.append(task)
                    print(f"   ✅ 生成连锁任务: {task.natural_description[:50]}...")

            # 清空连锁触发，避免重复处理
            state["execution_result"] = None

        elif isinstance(last_message, HumanMessage):
            # 处理用户输入，生成新任务入队
            user_input = last_message.content
            print(f"\n🎮 DM: {user_input}")

            task = planner_agent.plan(user_input)
            queue.append(task)

            print(f"🤖 PlannerAgent: 生成任务 - {task.natural_description}")
            print(f"   行动者: {task.actor}, 目标: {task.target}, 动作: {task.action}")

        # 从队列头部取任务（出队）作为当前任务
        if queue:
            state["current_task"] = queue.pop(0)
            state["task_queue"] = queue
            state["plan_approval_result"] = None  # 新任务需要审批
            print(f"\n📋 当前任务出队: {state['current_task'].natural_description[:50]}...")
            print(f"   队列剩余: {len(queue)} 个任务")
        else:
            state["current_task"] = None

        return state
    return planner_node


def dm_confirm_plan_node(state: AgentState) -> AgentState:
    """DM任务审批节点 - 手动确认"""
    task = state.get("current_task")
    if not task:
        return state

    print(f"\n" + "="*50)
    print(f"⏸️  DM 任务审批节点")
    print(f"="*50)
    print(f"任务: {task.natural_description}")
    print(f"行动者: {task.actor}")
    print(f"目标: {task.target}")
    print(f"动作: {task.action}")
    if task.context:
        print(f"\n执行上下文:")
        for k, v in task.context.items():
            print(f"  {k}: {v}")

    # 手动确认（支持直接输入修改建议）
    print("\n💡 提示: 输入 y 确认，n 拒绝，或直接输入修改建议")
    while True:
        response = input("> ").strip()
        lower = response.lower()

        if lower in ('y', 'yes'):
            print("✅ 已确认执行")
            state["plan_approval_result"] = True
            break
        elif lower in ('n', 'no'):
            print("❌ 已拒绝执行")
            state["plan_approval_result"] = False
            # 队列管理交给planner处理
            break
        elif response:  # 其他输入视为修改建议
            task.dm_notes = response
            print(f"✅ 已采纳修改建议并确认执行")
            print(f"   DM批注: {response[:80]}...")
            state["plan_approval_result"] = True
            break
        else:
            print("请输入 y(确认)、n(拒绝) 或修改建议")

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

        # 将变更转换为pending_changes格式（用于兼容）
        pending = []
        for change in result.field_changes:
            pending.append({
                "op": change.operation,
                "key": change.key,
                "field": change.field,
                "value": change.new_value
            })
        state["pending_changes"] = pending

        print(f"\n🎯 Executor: 执行完成")
        print(f"   生成 {len(result.field_changes)} 个字段变更")
        if result.triggered_chains:
            print(f"   检测到 {len(result.triggered_chains)} 个连锁触发")

        return state
    return executor_node


def next_task_node(state: AgentState) -> AgentState:
    """处理下一个任务或结束

    队列是"待执行"存储区，任务在planner中出队
    此节点只负责检查队列是否为空，重置状态
    """
    queue = state.get("task_queue", [])

    # 重置执行相关状态
    state["execution_result"] = None
    state["pending_changes"] = []
    state["applied_changes"] = []

    if queue:
        print(f"\n{'='*50}")
        print(f"📝 队列还有 {len(queue)} 个待执行任务")
    else:
        state["current_task"] = None
        print(f"\n{'='*50}")
        print("✅ 所有任务执行完成")

    return state


def has_triggered_chains(state: AgentState):
    """检测是否有连锁触发

    基于 ExecutionResult.triggered_chains 判断是否需要返回 Planner 处理连锁
    注意：任务已在planner中出队，这里只检测不修改队列
    """
    result: ExecutionResult | None = state.get("execution_result")

    if not result:
        logger.debug("无执行结果，无需处理连锁")
        return "next_task"

    triggered = result.triggered_chains

    if not triggered:
        logger.debug("无连锁触发")
        return "next_task"

    logger.info(f"检测到连锁触发", count=len(triggered), types=[t.get("type") for t in triggered])
    return "planner"


def should_continue_next_task(state: AgentState):
    """决定是否继续执行下一个任务

    如果有待执行的任务，继续；否则结束
    """
    queue = state.get("task_queue", [])

    # 检查是否还有未执行的任务（current_task已被移除，看队列中是否还有）
    if len(queue) > 0:
        logger.debug(f"继续执行下一个任务，队列长度: {len(queue)}")
        return "executor"

    logger.debug("任务队列为空，结束工作流")
    return "end"
