"""
核心类型定义

当前版本使用 Markdown 执行稿 + 受限 patch 来驱动执行流。
"""
from typing import TypedDict, Annotated, Any
from dataclasses import dataclass, field
from enum import Enum

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class Operation(Enum):
    """状态变更操作。"""

    ADD = "ADD"
    MOD = "MOD"
    DEL = "DEL"


@dataclass
class StateChange:
    """统一的状态变更记录。"""

    path: str
    old_value: Any
    new_value: Any
    operation: Operation
    source: str = ""


STEP_PHASES = {"declare", "choice", "action", "resolution"}


@dataclass
class ExecutionStep:
    """执行稿中的单个步骤。"""

    step_id: str
    title: str
    instruction: str
    status: str = "pending"  # pending | in_progress | completed | blocked
    phase: str = "declare"  # declare | choice | action | resolution
    depends_on: list[str] = field(default_factory=list)
    source: str = "planner"  # planner | rework


@dataclass
class StepUpdate:
    """Executor 对步骤状态的更新。"""

    step_id: str
    status: str
    note: str = ""


@dataclass
class ProposedFragment:
    """Executor 提出的可选新增效果。"""

    anchor_step_id: str
    insert_position: str  # before | after | replace_children
    reason: str
    fragment_summary: str
    required_context_keys: list[str] = field(default_factory=list)
    status: str = "pending"
    dm_note: str | None = None
    choice_title: str | None = None
    choice_prompt: str | None = None
    choice_response: str | None = None


@dataclass
class PlannedTask:
    """统一任务描述。"""

    task_id: str
    description: str
    context: str  # planner 产出的 Markdown 执行稿
    actor: str | None = None
    target: str | None = None
    source: str = "dm"  # dm | chain | system
    dm_notes: str | None = None
    task_category: str = "normal"  # normal | world_edit
    task_status: str = "pending"  # pending | completed | cancelled
    approval_granted: bool = False


@dataclass
class ExecutionScriptState:
    """运行时执行稿状态。"""

    task_id: str
    steps: list[ExecutionStep] = field(default_factory=list)
    active_step_id: str | None = None
    script_markdown: str = ""
    history: list[str] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """ExecutorAgent 执行结果。"""

    task_id: str
    success: bool
    field_changes: list[StateChange]
    narration: str
    step_updates: list[StepUpdate] = field(default_factory=list)
    proposed_fragment: ProposedFragment | None = None
    triggered_chains: list[dict[str, Any]] = field(default_factory=list)
    execution_context: dict[str, Any] = field(default_factory=dict)


class AgentState(TypedDict):
    """LangGraph Agent 状态。"""

    messages: Annotated[list[BaseMessage], add_messages]
    changes: Annotated[list[StateChange], lambda x, y: x + y]
    task_queue: list[PlannedTask]
    _current_task: PlannedTask | None
    _planned_message_count: int
    _execution_script: ExecutionScriptState | None
    _execution_context: dict[str, Any] | None
    _context_cache: dict[str, dict[str, Any]]
