"""
LangGraph状态定义
"""
from typing import TypedDict, Annotated, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from .task_intent import TaskIntent
from .paths import RelevantPaths
from .execution import ExecutionPlan
from .logic_result import LogicResult
from .state_change import StateChange
from .chain_trigger import ChainTrigger


class AgentState(TypedDict):
    """Agent状态"""
    messages: Annotated[list[BaseMessage], add_messages]
    
    # 任务相关
    current_task: TaskIntent | None
    task_queue: list[TaskIntent]
    
    # 状态摘要（LLM生成的人类可读摘要）
    state_summary: str | None
    
    # 检索到的规则（RagAgent输出）
    retrieved_rules: str | None
    
    # 执行相关
    relevant_paths: RelevantPaths | None  # 保留但可能不用
    execution_plan: ExecutionPlan | None
    current_step_idx: int
    step_results: list[LogicResult]
    
    # 状态变更
    pending_changes: list[dict]
    committed_changes: list[StateChange]
    
    # 连锁
    chain_triggers: list[ChainTrigger]
    
    # 人机协作
    pending_confirmation: dict | None
    confirmation_result: bool | None
    
    # 世界状态引用
    world_state: dict
