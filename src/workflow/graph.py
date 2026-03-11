"""
LangGraph工作流组装 - V5版本 (进一步简化)

流程:
planner -> dm_confirm_plan -> executor(write_fields工具) -> (检测连锁) -> planner (处理连锁)
                                                            ↓
                                                        (无连锁) -> next_task -> end

V5架构特点:
1. Executor 直接使用 write_fields 工具写入状态（不再需要Writer节点）
2. Executor 只保留 evaluate 和 write_fields 工具
3. 任务队列保持FIFO
4. DM批注通过 dm_notes 字段传递
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..types import AgentState
from ..agents import PlannerAgent, ExecutorAgent
from ..tools.toolkit import TrpgToolkit
from ..config import AppConfig

from .nodes import (
    create_planner_node,
    dm_confirm_plan_node,
    create_executor_node,
    next_task_node,
    should_continue_next_task,
    has_triggered_chains,
)


def create_workflow(
    config: AppConfig | None = None,
    world_state_path: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None
):
    """
    创建V4工作流 - 简化架构版本

    支持两种调用方式:
    1. 新方式: create_workflow(config=AppConfig.from_env())
    2. 旧方式: create_workflow(world_state_path=..., model=..., api_key=..., base_url=...)

    核心组件:
    - PlannerAgent: 合并意图识别+RAG+任务生成，统一处理所有任务（包括连锁任务）
    - ExecutorAgent: 执行计算+连锁检测，输出变更指令
    - Writer节点: 应用变更到KV状态

    流程:
    planner -> dm_confirm_plan -> executor -> writer
                                                ↓
                                        (有连锁?) -> planner
                                        (无连锁)  -> next_task -> end
    """
    # 兼容性处理：如果传入的是旧参数，转换为 AppConfig
    if config is None:
        config = AppConfig(
            world_state_path=world_state_path or "data/world_state.txt",
            llm_model=model or "gpt-4o",
            llm_api_key=api_key,
            llm_base_url=base_url,
        )

    # 初始化工具箱（内存模式，不写入文件）
    toolkit = TrpgToolkit(
        world_state_path=config.world_state_path,
        persist=config.persist_state
    )
    tools = toolkit.get_tools()
    tool_map = {t.name: t for t in tools}

    # Agent初始化
    planner_agent = PlannerAgent(
        model=config.llm_model,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
        tools=[tool_map["fetch_keys"], tool_map["read"], tool_map["search"]]
    )
    executor_agent = ExecutorAgent(
        model=config.llm_model,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
        tools=[tool_map["evaluate"], tool_map["write_fields"]]
    )

    # 创建工作流
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("planner", create_planner_node(planner_agent))
    workflow.add_node("dm_confirm_plan", dm_confirm_plan_node)
    workflow.add_node("executor", create_executor_node(executor_agent))

    # 设置入口
    workflow.set_entry_point("planner")

    # Planner 调度逻辑：
    # 1. 有current_task且未审批 -> dm_confirm
    # 2. 有current_task且已审批 -> executor
    # 3. 无current_task但有queue -> 继续出队（在planner内部处理）-> dm_confirm
    # 4. 都为空 -> 结束
    def route_from_planner(state: AgentState):
        """planner调度路由"""
        current = state.get("current_task")
        queue = state.get("task_queue", [])
        approval = state.get("plan_approval_result")
        
        if current:
            # 有当前任务
            if approval is True:
                # 已审批通过，去执行
                return "executor"
            elif approval is False:
                # 已拒绝，重置状态，让planner处理下一个
                state["plan_approval_result"] = None
                state["current_task"] = None
                # 如果有队列，继续；否则结束
                return "planner" if queue else "end"
            else:
                # 未审批，去审批
                return "dm_confirm"
        else:
            # 无当前任务，检查队列
            if queue:
                # 还有任务，让planner出队下一个
                return "planner"
            else:
                # 全部完成
                return "end"

    workflow.add_conditional_edges(
        "planner",
        route_from_planner,
        {
            "dm_confirm": "dm_confirm_plan",
            "executor": "executor",
            "planner": "planner",  # 自环，用于处理下一个任务
            "end": END,
        }
    )

    # dm_confirm 后回到 planner
    workflow.add_edge("dm_confirm_plan", "planner")

    # executor 后通过 has_triggered_chains 决定
    workflow.add_conditional_edges(
        "executor",
        has_triggered_chains,
        {
            "planner": "planner",
            "next_task": "planner",  # 无论有没有连锁，都回到planner调度
        }
    )

    # 编译
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory), toolkit.store
