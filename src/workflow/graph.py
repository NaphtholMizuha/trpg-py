"""
LangGraph工作流组装 - 扁平化队列架构

核心流程:
planner -> dm_decision -> resolution_builder -> decision_point_check -> resolution_runner -> planner
              ↓ 拒绝/完成
           planner (出队下一个)

架构特点:
1. 所有任务统一使用队列管理
2. 响应任务通过插队到队首实现优先级
3. 连锁任务执行后插队，确保尽快处理
4. 使用 interrupt 替代 input() 阻塞调用
5. 使用 Command(goto=...) 控制节点跳转
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from ..types import AgentState, StateChange, Operation, DecisionPoint, PlannedTask, ExecutionState
from ..agents import create_deep_planner_agent, ExecutorAgent
from ..tools.toolkit import TrpgToolkit
from ..config import AppConfig

from .nodes import (
    create_planner_node,
    create_dm_decision_node,
    create_context_builder_node,
    create_resolution_builder_node,
    create_decision_point_node,
    create_resolution_runner_node,
    create_executor_node,
)


def create_workflow(
    config: AppConfig | None = None,
    world_state_path: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None
):
    """
    创建扁平化队列工作流

    核心流程:
    - planner: 生成任务并入队，出队设置 _current_task
    - dm_decision: 统一审批节点，处理任务审批
    - context_builder: 注入 executor 可用的最小状态快照
    - resolution_builder: 构建当前任务的阶段化结算计划
    - decision_point_check: 在当前阶段检查决策窗口
    - resolution_runner: 推进结果阶段并在结束时生成连锁
    - executor: 执行派生的响应任务/世界编辑任务

    扁平化架构:
    - 所有任务统一使用队列 (FIFO) 管理
    - 响应任务通过插队到队首实现优先级
    - 连锁任务通过插队到队首实现“立即处理”
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
    planner_agent = create_deep_planner_agent(
        model=config.llm_model,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
        tools=[tool_map["fetch_keys"], tool_map["read"], tool_map["search"]],
        skill_names=None  # 加载所有 skills
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
    workflow.add_node("context_builder", create_context_builder_node(toolkit.store))
    workflow.add_node("resolution_builder", create_resolution_builder_node(executor_agent))
    workflow.add_node("decision_point_check", create_decision_point_node())
    workflow.add_node("resolution_runner", create_resolution_runner_node())
    workflow.add_node("executor", create_executor_node(executor_agent))

    # 设置入口
    workflow.set_entry_point("planner")

    # 编译
    serde = JsonPlusSerializer(
        allowed_msgpack_modules=[
            StateChange,
            Operation,
            DecisionPoint,
            PlannedTask,
            ExecutionState,
        ]
    )
    memory = MemorySaver(serde=serde)
    return workflow.compile(checkpointer=memory), toolkit.store
