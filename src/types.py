"""
核心类型定义 (V3版本)
"""
from typing import TypedDict, Annotated, Any
from dataclasses import dataclass, field
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# ============== 状态变更 ==============

@dataclass
class StateChange:
    """状态变更记录"""
    path: str
    old_value: Any
    new_value: Any
    operation: str = "set"


@dataclass
class KVChange:
    """KV 状态变更记录"""
    key: str
    old_value: str | None
    new_value: str | None
    operation: str


# ============== V3 任务类型 ==============

@dataclass
class PlannedTask:
    """PlannerAgent生成的任务"""
    task_id: str
    description: str  # 自然语言任务描述
    actor: str  # 行动者名称
    action: str = ""  # 动作描述
    target: str | None = None  # 目标名称
    context: dict = field(default_factory=dict)  # 执行上下文（如攻击加值、AC等数值）


@dataclass
class ExecutionResult:
    """ExecutorAgent执行结果"""
    task_id: str
    success: bool
    changes: list[StateChange]
    narration: str  # 执行过程描述


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
    """LangGraph Agent 状态 (V3版本)"""
    messages: Annotated[list[BaseMessage], add_messages]

    # 任务相关
    current_task: PlannedTask | None
    task_queue: list[PlannedTask]

    # 执行结果
    execution_result: ExecutionResult | None

    # 状态变更
    pending_changes: list[dict]
    committed_changes: list[StateChange]

    # 连锁
    chain_triggers: list[ChainTrigger]
    pending_chain_tasks: list[PlannedTask]  # 待审批的连锁任务
    chain_approval_result: bool | None  # DM审批结果

    # DM审批
    plan_approval_result: bool | None  # Planner任务审批


# ============== 辅助类型 ==============

@dataclass
class RelevantPaths:
    """相关路径集合（可选使用）"""
    read_paths: list[str] = field(default_factory=list)
    write_paths: list[str] = field(default_factory=list)
