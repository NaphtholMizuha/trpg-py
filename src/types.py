"""
核心类型定义
"""
from typing import TypedDict, Annotated, Any
from dataclasses import dataclass, field
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from .enums import TaskType


# ============== 任务相关 ==============

@dataclass
class TaskIntent:
    """任务意图"""
    task_id: str
    description: str  # 任务描述，如"艾尔德拉攻击地精"
    task_type: TaskType
    actor: str  # 行动者名称
    target: str | None = None  # 目标名称
    action: str = ""  # 动作描述
    context: dict = field(default_factory=dict)  # 额外上下文


# ============== 执行相关 ==============

@dataclass
class ExecutionStep:
    """执行步骤"""
    step_id: str
    description: str
    expression: str | None = None  # 逻辑表达式
    condition: str = "总是"  # 执行条件
    state_changes: list[dict] = field(default_factory=list)


@dataclass
class ExecutionPlan:
    """执行计划"""
    task_id: str
    steps: list[ExecutionStep]
    required_rules: list[str] = field(default_factory=list)


@dataclass
class LogicResult:
    """逻辑执行结果"""
    success: bool
    result: Any
    resolved_paths: dict
    trace: list[str]


# ============== 状态变更 ==============

@dataclass
class StateChange:
    """状态变更记录"""
    path: str
    old_value: Any
    new_value: Any
    operation: str = "set"


# ============== 连锁相关 ==============

@dataclass
class ChainTrigger:
    """连锁触发器"""
    priority: int  # 优先级
    condition: str  # 触发条件
    effect: str  # 触发效果
    source_path: str = ""  # 触发源路径


# ============== Agent 状态 ==============

class AgentState(TypedDict):
    """LangGraph Agent 状态"""
    messages: Annotated[list[BaseMessage], add_messages]
    
    # 任务相关
    current_task: TaskIntent | None
    task_queue: list[TaskIntent]
    
    # 状态摘要
    state_summary: str | None
    
    # 检索到的规则
    retrieved_rules: str | None
    
    # 执行相关
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


# ============== 其他辅助类型 ==============

@dataclass
class RelevantPaths:
    """相关路径集合（可选使用）"""
    read_paths: list[str] = field(default_factory=list)
    write_paths: list[str] = field(default_factory=list)
