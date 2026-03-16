"""
LangGraph工作流组装 - V8版本 (统一DM决策 + 队列管理)

流程:
planner -> dm_decision -> executor -> dm_decision -> planner
              ↓ 拒绝/批准              ↓ 无连锁/有连锁
           (自动出队下一个)          (连锁插队头部优先)

V8架构特点:
1. 统一DM决策节点：任务审批和连锁审批合并
2. 队列管理：入队尾部、插队头部、出队
3. 事件驱动状态流转
4. Planner预判反应，Executor验证，DM决策
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..types import AgentState
from ..agents import PlannerAgent, ExecutorAgent
from ..tools.toolkit import TrpgToolkit
from ..config import AppConfig

from .nodes import (
    create_planner_node,
    create_executor_node,
    create_dm_decision_node,
    route_after_planner,
    route_after_dm_decision,
    route_after_executor,
)


def create_workflow(
    config: AppConfig | None = None,
    world_state_path: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None
):
    """
    创建V8工作流 (统一DM决策 + 队列管理)

    核心流程:
    - planner: 入队/插队任务，出队生成 TaskCreated
    - dm_decision: 统一审批节点，处理任务审批和连锁审批
    - executor: 执行任务，生成 ExecutionCompleted
    - (回到planner): 处理完成事件，出队下一个任务

    反应机制:
    - Planner预判可能反应 -> Executor验证条件 -> DM决策是否触发
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
    workflow.add_node("dm_decision", create_dm_decision_node())
    workflow.add_node("executor", create_executor_node(executor_agent))

    # 设置入口
    workflow.set_entry_point("planner")

    # === 条件边定义 ===

    # planner -> dm_decision (有TaskCreated) / END (无)
    workflow.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "dm_decision": "dm_decision",
            "end": END,
        }
    )

    # dm_decision -> executor (任务审批通过) / planner (其他情况)
    workflow.add_conditional_edges(
        "dm_decision",
        route_after_dm_decision,
        {
            "executor": "executor",
            "planner": "planner",
        }
    )

    # executor -> dm_decision (有连锁) / planner (无连锁)
    workflow.add_conditional_edges(
        "executor",
        route_after_executor,
        {
            "dm_decision": "dm_decision",
            "planner": "planner",
        }
    )

    # 编译
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory), toolkit.store
