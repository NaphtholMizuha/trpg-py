"""
LangGraph工作流组装 - V7版本 (队列管理 + 事件驱动)

流程:
planner -> dm_confirm_plan -> executor -> dm_confirm_chain -> planner
              ↓ 拒绝/批准              ↓ 无连锁/有连锁
           (自动出队下一个)          (连锁插队头部优先)

V7架构特点:
1. 队列管理：入队尾部、插队头部、出队
2. 连锁任务插队头部，优先执行
3. 事件驱动状态流转
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
    create_chain_confirm_node,
    route_after_planner,
    route_after_plan_confirm,
    route_after_executor,
    route_after_chain_confirm,
)


def create_workflow(
    config: AppConfig | None = None,
    world_state_path: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None
):
    """
    创建V7工作流 (队列管理 + 事件驱动)

    核心流程:
    - planner: 入队/插队任务，出队生成 TaskCreated
    - dm_confirm_plan: 审批任务，生成 TaskApproved
    - executor: 执行任务，生成 ExecutionCompleted
    - dm_confirm_chain: 审批连锁，生成 ChainApproved/Rejected
    - (回到planner): 处理完成事件，出队下一个任务
    """
    # 兼容性处理
    if config is None:
        config = AppConfig(
            world_state_path=world_state_path or "data/world_state.txt",
            llm_model=model or "gpt-4o",
            llm_api_key=api_key,
            llm_base_url=base_url,
        )

    # 初始化工具箱
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
    workflow.add_node("dm_confirm_chain", create_chain_confirm_node())

    # 设置入口
    workflow.set_entry_point("planner")

    # === 条件边定义 ===

    # planner -> dm_confirm_plan (有TaskCreated) / END (无)
    workflow.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "dm_confirm_plan": "dm_confirm_plan",
            "end": END,
        }
    )

    # dm_confirm_plan -> executor (通过) / planner (拒绝/修改)
    workflow.add_conditional_edges(
        "dm_confirm_plan",
        route_after_plan_confirm,
        {
            "executor": "executor",
            "planner": "planner",
        }
    )

    # executor -> dm_confirm_chain (有连锁) / planner (无连锁)
    workflow.add_conditional_edges(
        "executor",
        route_after_executor,
        {
            "dm_confirm_chain": "dm_confirm_chain",
            "planner": "planner",
        }
    )

    # dm_confirm_chain -> planner (统一回到planner处理队列)
    workflow.add_conditional_edges(
        "dm_confirm_chain",
        route_after_chain_confirm,
        {
            "planner": "planner",
        }
    )

    # 编译
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory), toolkit.store
