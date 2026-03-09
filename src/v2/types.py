"""
V2 Agent 核心类型定义
"""
from typing import TypedDict, Annotated, Any
from dataclasses import dataclass, field
from enum import Enum
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class TaskType(Enum):
    """任务类型"""
    ATTACK = "attack"           # 物理攻击
    SPELL = "spell"             # 法术
    INTERACT = "interact"       # 环境互动
    MOVE = "move"               # 移动


@dataclass
class TaskIntent:
    """任务意图 - InterfaceAgent 的输出"""
    task_id: str
    description: str           # 任务描述
    task_type: TaskType        # 任务类型
    actor: str                 # 行动者实体ID或名称
    target: str | None         # 目标实体ID或名称
    action: str                # 具体动作
    context: dict = field(default_factory=dict)  # 额外上下文


@dataclass  
class RelevantPaths:
    """PathFinder 返回的相关路径"""
    primary_paths: dict[str, str]   # {path: type}
    related_paths: dict[str, str]   # {path: type}


@dataclass
class ExecutionStep:
    """执行步骤"""
    step_id: str
    description: str           # 步骤描述
    expression: str | None     # 逻辑表达式（如果有）
    condition: str | None      # 执行条件（如"命中"）
    state_changes: list[dict]  # 计划的状态变更


@dataclass
class ExecutionPlan:
    """执行计划 - TaskAgent 的输出"""
    task_id: str
    steps: list[ExecutionStep]
    required_rules: list[str]  # 需要查询的规则


@dataclass
class LogicResult:
    """LogicRunner 执行结果"""
    success: bool
    result: Any
    resolved_paths: dict[str, Any]  # 解析的路径及实际值（用于审计）
    trace: list[str]                # 执行轨迹


@dataclass
class StateChange:
    """状态变更记录"""
    path: str
    old_value: Any
    new_value: Any
    operation: str  # set, add, subtract


@dataclass
class ChainTrigger:
    """连锁触发条件"""
    condition: str      # 触发条件表达式
    effect: str         # 效果描述
    priority: int       # 优先级


# LangGraph 状态
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    
    # 任务相关
    current_task: TaskIntent | None
    task_queue: list[TaskIntent]
    
    # 执行相关
    relevant_paths: RelevantPaths | None
    execution_plan: ExecutionPlan | None
    current_step_idx: int
    step_results: list[LogicResult]
    
    # 状态变更
    pending_changes: list[dict]  # 待确认的状态变更
    committed_changes: list[StateChange]  # 已提交的状态变更
    
    # 连锁
    chain_triggers: list[ChainTrigger]
    
    # 人机协作
    pending_confirmation: dict | None
    confirmation_result: bool | None
    
    # 世界状态引用（实际状态由StateWriter管理）
    world_state: dict
