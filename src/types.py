"""
核心类型定义

当前版本的重点是使用通用 DecisionPoint 表达规则相关的决策窗口，
避免将工作流绑定到某一种 TRPG 规则术语。
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


class DecisionTiming(str, Enum):
    """引擎级决策窗口时机

    这些 timing 由工作流定义，规则系统通过 metadata 解释细节。
    """
    BEFORE_ACTION = "before_action"
    BEFORE_RESOLUTION = "before_resolution"
    BEFORE_CONSEQUENCE = "before_consequence"
    AFTER_CONSEQUENCE = "after_consequence"
    AFTER_ACTION = "after_action"


VALID_DECISION_TIMINGS = {timing.value for timing in DecisionTiming}


def normalize_decision_timing(value: str | None) -> str:
    """将 LLM 或外部输入的 timing 归一化到引擎支持的常量。"""
    if not value:
        return DecisionTiming.BEFORE_RESOLUTION.value

    raw = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "before_cast": DecisionTiming.BEFORE_ACTION.value,
        "on_cast_declared": DecisionTiming.BEFORE_ACTION.value,
        "before_spell_resolution": DecisionTiming.BEFORE_RESOLUTION.value,
        "before_damage_resolution": DecisionTiming.BEFORE_CONSEQUENCE.value,
        "before_damage": DecisionTiming.BEFORE_CONSEQUENCE.value,
        "before_effect": DecisionTiming.BEFORE_CONSEQUENCE.value,
        "after_damage": DecisionTiming.AFTER_CONSEQUENCE.value,
        "after_effect": DecisionTiming.AFTER_CONSEQUENCE.value,
        "after_resolution": DecisionTiming.AFTER_ACTION.value,
    }
    normalized = aliases.get(raw, raw)
    if normalized in VALID_DECISION_TIMINGS:
        return normalized
    return DecisionTiming.BEFORE_RESOLUTION.value


# ============== 核心数据类型 ==============

@dataclass
class StateChange:
    """统一的状态变更记录"""
    path: str
    old_value: Any
    new_value: Any
    operation: Operation
    source: str = ""  # 来源task_id


@dataclass
class DecisionPoint:
    """通用决策窗口

    不预设“反应”“法术”等规则名词，只描述：
    - 谁可以做决定（decider）
    - 当前是什么时机（timing）
    - 可选的响应动作/能力（option_name）
    - 出现此窗口的条件与说明
    """
    condition: str
    decider: str
    description: str
    timing: str = DecisionTiming.BEFORE_RESOLUTION.value
    option_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class PlannedTask:
    """统一任务描述

    任务类型:
    - normal: 普通任务（攻击、施法、移动等）
    - world_edit: 直接世界修改
    - decision_response: 由决策窗口派生出的响应动作
    """
    task_id: str
    description: str  # 一句话描述（给玩家/DM看的）
    context: str  # 完整规划文本（给Executor看的）
    actor: str | None = None  # 仅用于快速筛选/显示
    target: str | None = None  # 仅用于快速筛选/显示
    source: str = "dm"  # "dm" | "chain" | "system"
    dm_notes: str | None = None  # DM审批时的批注

    # 任务分类和状态
    task_category: str = "normal"  # "normal" | "world_edit" | "decision_response"
    task_status: str = "pending"  # "pending" | "waiting_decision" | "completed" | "cancelled"
    related_task_id: str | None = None  # 关联任务ID（派生响应动作关联原任务）
    approval_granted: bool = False  # 是否已完成 DM 审批，恢复执行时可跳过重复审批

    # 可能出现的决策窗口
    decision_points: list[DecisionPoint] = field(default_factory=list)


@dataclass
class ResolutionItem:
    """阶段化结算中的单个项目。"""
    kind: str  # "decision_point" | "state_change" | "chain"
    timing: str
    payload: dict[str, Any]


@dataclass
class ExecutionState:
    """运行时结算状态，用于阶段化推进当前主任务。"""
    task_id: str
    phase_index: int = 0
    phases: list[str] = field(default_factory=list)
    narration: str = ""
    direct_changes: list[StateChange] = field(default_factory=list)
    consequence_changes: list[StateChange] = field(default_factory=list)
    after_changes: list[StateChange] = field(default_factory=list)
    decision_points: list[DecisionPoint] = field(default_factory=list)
    triggered_chains: list[dict[str, Any]] = field(default_factory=list)
    resolution_effects: list[dict[str, Any]] = field(default_factory=list)
    execution_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """ExecutorAgent执行结果"""
    task_id: str
    success: bool
    field_changes: list[StateChange]
    narration: str
    execution_context: dict = field(default_factory=dict)
    triggered_chains: list[dict] = field(default_factory=list)
    consequence_changes: list[StateChange] = field(default_factory=list)
    decision_points: list[DecisionPoint] = field(default_factory=list)
    resolution_effects: list[dict[str, Any]] = field(default_factory=list)


# ============== Agent 状态 (V6 - LangGraph 原生版) ==============

class AgentState(TypedDict):
    """LangGraph Agent 状态 (V6版本 - 使用 interrupt 和 Command)

    设计变更：
    - messages: 对话历史
    - changes: 所有状态变更的历史记录
    - task_queue: 待处理任务队列
    - _current_task: 当前正在处理的任务（瞬态）
    - _pending_interrupt: 中断请求（用于人机交互）
    """
    messages: Annotated[list[BaseMessage], add_messages]
    changes: Annotated[list[StateChange], lambda x, y: x + y]
    task_queue: list[PlannedTask]
    _current_task: PlannedTask | None
    _pending_interrupt: dict | None  # 人机交互中断请求
    _planned_message_count: int  # 已消费的 messages 长度，避免回环时重复规划
    _execution_state: ExecutionState | None
    _execution_context: dict[str, Any] | None


# ============== 辅助类型 ==============

@dataclass
class RelevantPaths:
    """相关路径集合（可选使用）"""
    read_paths: list[str] = field(default_factory=list)
    write_paths: list[str] = field(default_factory=list)
