"""
LangGraph工作流组装 - V3版本

流程:
planner -> dm_confirm_plan -> executor -> chain_agent -> dm_confirm_chain -> next_task
                                     ^___________________________|
                                          (有连锁任务且DM确认)
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..types import AgentState
from ..agents import PlannerAgent, ExecutorAgent, ChainAgent
from ..tools.toolkit import TrpgToolkit

from .nodes import (
    create_planner_node,
    dm_confirm_plan_node,
    create_executor_node,
    create_chainagent_node,
    dm_confirm_chain_node,
    next_task_node,
    should_continue_chain,
    should_continue_next_task,
)


def create_workflow(
    world_state_path: str = "data/world_state.txt",
    model: str = "gpt-4o",
    api_key: str | None = None,
    base_url: str | None = None
):
    """
    创建V3工作流 - Agent架构版本

    核心组件:
    - PlannerAgent: 合并意图识别+RAG+任务生成
    - ExecutorAgent: 合并逻辑计算+状态写入
    - ChainAgent: 连锁检测，支持Tools

    流程:
    planner -> dm_confirm_plan -> executor -> chain_agent -> dm_confirm_chain
                                                  ^               |
                                                  |_______________|
    """
    # 初始化工具箱（内存模式，不写入文件）
    toolkit = TrpgToolkit(world_state_path=world_state_path, persist=False)
    tools = toolkit.get_tools()
    tool_map = {t.name: t for t in tools}

    # Agent初始化
    planner_agent = PlannerAgent(
        model=model, api_key=api_key, base_url=base_url,
        tools=[tool_map["fetch_keys"], tool_map["read"], tool_map["search"]]
    )
    executor_agent = ExecutorAgent(
        model=model, api_key=api_key, base_url=base_url,
        tools=[tool_map["fetch_keys"], tool_map["read"], tool_map["evaluate"], tool_map["write"]]
    )
    chain_agent = ChainAgent(
        model=model, api_key=api_key, base_url=base_url,
        tools=[tool_map["fetch_keys"], tool_map["read"], tool_map["search"]]
    )

    # 创建工作流
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("planner", create_planner_node(planner_agent))
    workflow.add_node("dm_confirm_plan", dm_confirm_plan_node)
    workflow.add_node("executor", create_executor_node(executor_agent))
    workflow.add_node("chain_agent", create_chainagent_node(chain_agent))
    workflow.add_node("dm_confirm_chain", dm_confirm_chain_node)
    workflow.add_node("next_task", next_task_node)

    # 设置入口
    workflow.set_entry_point("planner")

    # 添加边
    workflow.add_edge("planner", "dm_confirm_plan")
    workflow.add_edge("dm_confirm_plan", "executor")
    workflow.add_edge("executor", "chain_agent")

    # 连锁条件边
    workflow.add_conditional_edges(
        "chain_agent",
        should_continue_chain,
        {
            "dm_confirm_chain": "dm_confirm_chain",
            "next_task": "next_task"
        }
    )

    workflow.add_edge("dm_confirm_chain", "next_task")

    # 下一个任务条件边
    workflow.add_conditional_edges(
        "next_task",
        should_continue_next_task,
        {
            "executor": "executor",
            "end": END
        }
    )

    # 编译
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory), toolkit.store
