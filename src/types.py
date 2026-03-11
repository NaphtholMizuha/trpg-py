"""
核心类型定义 (V3版本)
"""
from typing import TypedDict, Annotated, Any
from dataclasses import dataclass, field
from enum import Enum
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# ============== 枚举类型 ==============

class TaskSource(Enum):
    """任务来源"""
    DM = "dm"
    CHAIN = "chain"
    SYSTEM = "system"


class Operation(Enum):
    """状态变更操作"""
    ADD = "ADD"
    MOD = "MOD"
    DEL = "DEL"


# ============== 状态变更 ==============

@dataclass
class StateChange:
    """状态变更记录"""
    path: str
    old_value: Any
    new_value: Any
    operation: Operation = Operation.MOD  # 使用枚举


@dataclass
class KVChange:
    """KV 状态变更记录"""
    key: str
    old_value: str | None
    new_value: str | None
    operation: str


# ============== 连锁相关 ==============

@dataclass
class PotentialChain:
    """Planner预判的可能连锁"""
    condition: str       # 触发条件描述，如"目标HP降至0"
    chain_type: str      # 连锁类型标记，如"death", "explosion", "concentration"
    description: str     # 连锁效果描述


# ============== V3 任务类型 ==============

@dataclass
class PlannedTask:
    """统一任务描述 - 自然语言为主，结构化字段可选"""
    task_id: str
    natural_description: str  # 核心：自然语言描述包含所有信息
    actor: str | None = None  # 可选，可从描述中解析
    target: str | None = None  # 可选
    action: str = ""  # 可选
    context: dict = field(default_factory=dict)  # 执行上下文（保留向后兼容）
    source: str = "dm"  # "dm" | "chain" | "system"，标记任务来源
    requires_confirmation: bool = False  # 新增：是否需要DM确认
    priority: int = 0  # 新增：任务优先级
    potential_chains: list[PotentialChain] = field(default_factory=list)  # 可能触发的连锁
    dm_notes: str | None = None  # DM审批时的批注/修改建议


@dataclass
class FieldChange:
    """字段级变更指令"""
    key: str          # KV key，如 "Aldera.combat"
    field: str        # 字段名，如 "HP"
    old_value: str    # 旧值
    new_value: str    # 新值
    operation: str = "MOD"  # ADD/MOD/DEL


@dataclass
class ExecutionResult:
    """ExecutorAgent执行结果"""
    task_id: str
    success: bool
    field_changes: list[FieldChange]  # 字段级变更指令（给Writer用）
    narration: str  # 执行过程描述
    execution_context: dict = field(default_factory=dict)  # 执行上下文（给Planner连锁检测）
    triggered_chains: list[dict] = field(default_factory=list)  # 检测到的连锁触发




@dataclass
class ChainTrigger:
    """连锁触发器"""
    priority: int  # 优先级
    condition: str  # 触发条件
    effect: str  # 触发效果
    source_path: str = ""  # 触发源路径


# ============== Agent 状态 ==============

class AgentState(TypedDict):
    """LangGraph Agent 状态 (V4版本 - 简化架构)"""
    messages: Annotated[list[BaseMessage], add_messages]

    # 任务相关
    current_task: PlannedTask | None
    task_queue: list[PlannedTask]

    # 执行结果
    execution_result: ExecutionResult | None

    # 状态变更
    applied_changes: list[StateChange]  # Writer应用后的变更
    pending_changes: list[dict]
    committed_changes: list[StateChange]

    # DM审批
    plan_approval_result: bool | None  # 统一的任务审批

    # 元数据
    metadata: dict


# ============== 辅助类型 ==============

@dataclass
class RelevantPaths:
    """相关路径集合（可选使用）"""
    read_paths: list[str] = field(default_factory=list)
    write_paths: list[str] = field(default_factory=list)
