"""
核心类型定义 (V4版本 - 事件驱动架构)

主要变更:
1. 统一变更类型 StateChange，移除 FieldChange/KVChange
2. 引入 Event 系统，替代临时状态字段
3. 简化 AgentState，移除冗余字段
"""
from typing import TypedDict, Annotated, Any
from dataclasses import dataclass, field
from enum import Enum
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# ============== 枚举类型 ==============

class Operation(Enum):
    """状态变更操作"""
    ADD = "ADD"
    MOD = "MOD"
    DEL = "DEL"


class TaskSource(Enum):
    """任务来源"""
    DM = "dm"
    CHAIN = "chain"
    SYSTEM = "system"


# ============== 事件系统 ==============

@dataclass
class Event:
    """事件基类"""
    source: str  # 事件来源节点


@dataclass
class TaskCreated(Event):
    """任务创建事件 - planner生成任务后发出"""
    task: "PlannedTask"


@dataclass
class TaskApproved(Event):
    """任务审批通过事件 - dm确认后发出"""
    task: "PlannedTask"
    dm_notes: str | None = None


@dataclass
class TaskRejected(Event):
    """任务被拒绝事件"""
    task: "PlannedTask"
    reason: str | None = None


@dataclass
class ExecutionCompleted(Event):
    """执行完成事件 - executor执行后发出"""
    task_id: str
    success: bool
    narration: str
    changes: list["StateChange"]  # 状态变更列表
    triggered_chains: list[dict] = field(default_factory=list)


@dataclass
class ChainApproved(Event):
    """连锁触发审批通过事件"""
    chain_type: str
    description: str
    source_key: str


@dataclass
class ChainRejected(Event):
    """连锁触发被拒绝事件"""
    chain_type: str


@dataclass
class WorkflowEnd(Event):
    """工作流结束事件"""
    reason: str


# ============== 核心数据类型 ==============

@dataclass
class StateChange:
    """统一的状态变更记录

    合并了原来的 StateChange 和 FieldChange：
    - path: 统一路径表示，如 "Aldera.combat.HP" 或 "party.inventory"
    - operation: 操作类型
    - old_value/new_value: 变更前后值
    - source: 变更来源（task_id）
    """
    path: str
    old_value: Any
    new_value: Any
    operation: Operation
    source: str = ""  # 来源task_id


@dataclass
class PlannedTask:
    """统一任务描述 - 自然语言为主，结构化字段可选"""
    task_id: str
    description: str  # 一句话描述（给玩家/DM看的）
    context: str  # 完整规划文本（给Executor看的）
    actor: str | None = None  # 仅用于快速筛选/显示
    target: str | None = None  # 仅用于快速筛选/显示
    source: str = "dm"  # "dm" | "chain" | "system"
    dm_notes: str | None = None  # DM审批时的批注


@dataclass
class ExecutionResult:
    """ExecutorAgent执行结果"""
    task_id: str
    success: bool
    field_changes: list[StateChange]  # 改为 StateChange
    narration: str
    execution_context: dict = field(default_factory=dict)
    triggered_chains: list[dict] = field(default_factory=list)


@dataclass
class PotentialChain:
    """Planner预判的可能连锁"""
    condition: str       # 触发条件描述
    chain_type: str      # 连锁类型标记
    description: str     # 连锁效果描述


# ============== Agent 状态 (V4 - 事件驱动) ==============

class AgentState(TypedDict):
    """LangGraph Agent 状态 (V4版本 - 事件驱动架构)

    简化设计：
    - messages: 对话历史（LangGraph自动管理）
    - changes: 所有状态变更的历史记录
    - task_queue: 待处理任务队列
    - metadata: 元数据
    - _event: 瞬态事件，单次消费后即清空
    - _current_task: 瞬态当前任务
    """
    messages: Annotated[list[BaseMessage], add_messages]

    # 历史记录
    changes: Annotated[list[StateChange], lambda x, y: x + y]

    # 任务队列
    task_queue: list[PlannedTask]

    # 元数据
    metadata: dict

    # 瞬态字段（单次流转，以下划线标记）
    _event: Event | None
    _current_task: PlannedTask | None


# ============== 辅助类型 ==============

@dataclass
class RelevantPaths:
    """相关路径集合（可选使用）"""
    read_paths: list[str] = field(default_factory=list)
    write_paths: list[str] = field(default_factory=list)
