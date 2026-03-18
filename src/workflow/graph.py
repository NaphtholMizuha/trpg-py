"""
LangGraph 工作流组装 - 最小骨架

核心流程:
planner -> task_approval -> executor -> commiter -> planner
"""
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from ..types import (
    AgentState,
    ExecutionResult,
    StateChange,
    Operation,
    TaskExecution,
)
from ..agents import create_deep_planner_agent, ExecutorAgent
from ..tools.toolkit import TrpgToolkit
from ..config import AppConfig

from .nodes import (
    create_planner_node,
    create_task_approval_node,
    create_commiter_node,
    create_executor_node,
)


def create_workflow(
    config: AppConfig | None = None,
    world_state_path: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
):
    if config is None:
        config = AppConfig(
            world_state_path=world_state_path or "data/world_state.txt",
            llm_model=model or "gpt-4o",
            llm_api_key=api_key,
            llm_base_url=base_url,
        )

    toolkit = TrpgToolkit(
        world_state_path=config.world_state_path,
        persist=config.persist_state,
    )
    tools = toolkit.get_tools()
    tool_map = {t.name: t for t in tools}

    planner_agent = create_deep_planner_agent(
        model=config.llm_model,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
        tools=[tool_map["fetch_keys"], tool_map["read"], tool_map["search"]],
        skill_names=None,
    )
    executor_agent = ExecutorAgent(
        model=config.llm_model,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
        tools=[tool_map["evaluate"]],
    )

    workflow = StateGraph(AgentState)
    workflow.add_node("planner", create_planner_node(planner_agent))
    workflow.add_node("task_approval", create_task_approval_node())
    workflow.add_node("executor", create_executor_node(executor_agent))
    workflow.add_node("commiter", create_commiter_node(tool_map["write_fields"]))

    workflow.set_entry_point("planner")

    serde = JsonPlusSerializer(
        allowed_msgpack_modules=[
            ExecutionResult,
            StateChange,
            Operation,
            TaskExecution,
        ]
    )
    memory = MemorySaver(serde=serde)
    return workflow.compile(checkpointer=memory), toolkit.store
