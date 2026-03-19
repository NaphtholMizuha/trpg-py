"""
核心类型定义。
"""
from typing import TypedDict, Annotated, Any, Literal
from enum import Enum
import re

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Operation(Enum):
    """状态变更操作。"""

    ADD = "ADD"
    MOD = "MOD"
    DEL = "DEL"


class WindowStatus(Enum):
    """结算窗口状态。"""

    OPEN = "open"
    READY = "ready"
    RESOLVED = "resolved"


class StateChange(BaseModel):
    """统一的状态变更记录。"""

    model_config = ConfigDict(extra="forbid")

    path: str
    old_value: str | None = None
    new_value: str | None = None
    operation: Operation
    source: str = ""


def _stringify_change_values(items: Any) -> Any:
    """将 field_changes / discarded_field_changes 中的 old/new value 归一为字符串。"""
    if items is None or items == {}:
        return []
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        return items

    normalized_items: list[Any] = []
    for item in items:
        if not isinstance(item, dict):
            normalized_items.append(item)
            continue

        normalized_item = dict(item)
        for value_key in ("old_value", "new_value"):
            value = normalized_item.get(value_key)
            if value is None or isinstance(value, str):
                continue
            normalized_item[value_key] = str(value)
        normalized_items.append(normalized_item)
    return normalized_items


class TaskExecution(BaseModel):
    """Planner 输出并在工作流中流转的单步任务。"""

    model_config = ConfigDict(extra="forbid")

    task_id: str = ""
    description: str
    context: str
    action_type: str = "自定义"
    execution_steps: list[str] = Field(default_factory=list)
    write_targets: list[str] = Field(default_factory=list)
    actor: str | None = None
    target: str | None = None
    source: Literal["dm", "chain", "system"] = "dm"
    dm_notes: str | None = None
    task_category: Literal["normal", "world_edit"] = "normal"

    @model_validator(mode="before")
    @classmethod
    def normalize_loose_task(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        normalized.pop("raw_query_appendix", None)

        for field_name in (
            "execution_steps",
            "write_targets",
        ):
            value = normalized.get(field_name)
            if value is None or value == {}:
                normalized[field_name] = []
            elif isinstance(value, str):
                normalized[field_name] = [value]

        return normalized


class TriggeredChain(BaseModel):
    """Executor 返回的后续链式任务。"""

    model_config = ConfigDict(extra="forbid")

    task_id: str = ""
    description: str
    context: str = ""
    actor: str | None = None
    target: str | None = None
    dm_notes: str | None = None
    task_category: Literal["normal", "world_edit"] = "normal"


class ExecutionResult(BaseModel):
    """ExecutorAgent 执行结果。"""

    model_config = ConfigDict(extra="forbid")

    task_id: str = ""
    success: bool = False
    field_changes: list[StateChange] = Field(default_factory=list)
    narration: str = ""
    triggered_chains: list[TriggeredChain] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_loose_result(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)

        normalized["field_changes"] = _stringify_change_values(normalized.get("field_changes"))

        triggered_chains = normalized.get("triggered_chains")
        if triggered_chains is None or triggered_chains == {}:
            normalized["triggered_chains"] = []
        elif isinstance(triggered_chains, dict):
            normalized["triggered_chains"] = [triggered_chains]

        if normalized.get("narration") is None:
            normalized["narration"] = ""

        return normalized


class ResolutionWindowRun(BaseModel):
    """结算窗口中的单次 executor 结果。"""

    model_config = ConfigDict(extra="forbid")

    order: int = Field(ge=0)
    priority: int = Field(default=100)
    task_id: str = ""
    description: str
    actor: str | None = None
    target: str | None = None
    narration: str = ""
    state_snapshot: dict[str, str] = Field(default_factory=dict)
    field_changes: list[StateChange] = Field(default_factory=list)
    triggered_chains: list[TriggeredChain] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_loose_run(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)

        state_snapshot = normalized.get("state_snapshot")
        if state_snapshot is None or state_snapshot == {}:
            normalized["state_snapshot"] = {}

        normalized["field_changes"] = _stringify_change_values(normalized.get("field_changes"))

        triggered_chains = normalized.get("triggered_chains")
        if triggered_chains is None or triggered_chains == {}:
            normalized["triggered_chains"] = []
        elif isinstance(triggered_chains, dict):
            normalized["triggered_chains"] = [triggered_chains]

        if normalized.get("narration") is None:
            normalized["narration"] = ""

        return normalized

    @classmethod
    def from_task_and_result(
        cls,
        task: TaskExecution,
        result: ExecutionResult,
        *,
        order: int,
        priority: int,
    ) -> "ResolutionWindowRun":
        """把当前工作流中的任务与执行结果收敛成 window run。"""
        return cls(
            order=order,
            priority=priority,
            task_id=result.task_id or task.task_id,
            description=task.description,
            actor=task.actor,
            target=task.target,
            narration=result.narration,
            state_snapshot=_build_task_state_snapshot(task),
            field_changes=result.field_changes,
            triggered_chains=result.triggered_chains,
        )


class ResolutionWindow(BaseModel):
    """同一结算窗口内待 resolver 合并的输入。"""

    model_config = ConfigDict(extra="forbid")

    window_id: str
    root_task_id: str = ""
    root_description: str
    status: WindowStatus = WindowStatus.OPEN
    shared_context: list[str] = Field(default_factory=list)
    state_snapshot: dict[str, str] = Field(default_factory=dict)
    runs: list[ResolutionWindowRun] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_loose_window(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)

        shared_context = normalized.get("shared_context")
        if shared_context is None or shared_context == {}:
            normalized["shared_context"] = []
        elif isinstance(shared_context, str):
            normalized["shared_context"] = [shared_context]

        state_snapshot = normalized.get("state_snapshot")
        if state_snapshot is None or state_snapshot == {}:
            normalized["state_snapshot"] = {}

        runs = normalized.get("runs")
        if runs is None or runs == {}:
            normalized["runs"] = []
        elif isinstance(runs, dict):
            normalized["runs"] = [runs]

        return normalized


class DiscardedStateChange(StateChange):
    """resolver 判定为不生效的字段变更。"""

    reason: str
    discarded_by: str = ""


class ResolutionResult(BaseModel):
    """resolver 的合并输出。"""

    model_config = ConfigDict(extra="forbid")

    window_id: str
    final_field_changes: list[StateChange] = Field(default_factory=list)
    discarded_field_changes: list[DiscardedStateChange] = Field(default_factory=list)
    resolution_summary: str = ""
    dm_suggestions: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_loose_resolution(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)

        normalized["final_field_changes"] = _stringify_change_values(normalized.get("final_field_changes"))

        normalized["discarded_field_changes"] = _stringify_change_values(
            normalized.get("discarded_field_changes")
        )

        dm_suggestions = normalized.get("dm_suggestions")
        if dm_suggestions is None or dm_suggestions == {}:
            normalized["dm_suggestions"] = []
        elif isinstance(dm_suggestions, str):
            normalized["dm_suggestions"] = [dm_suggestions]

        if normalized.get("resolution_summary") is None:
            normalized["resolution_summary"] = ""

        return normalized


class AgentState(TypedDict):
    """LangGraph Agent 状态。"""

    messages: Annotated[list[BaseMessage], add_messages]
    changes: Annotated[list[StateChange], lambda x, y: x + y]
    task_queue: list[TaskExecution]
    _current_task: TaskExecution | None
    _planned_message_count: int
    _execution_result: ExecutionResult | None
    active_window: ResolutionWindow | None
    pending_resolution: ResolutionResult | None
    pending_window_priority: int | None
    window_counter: int


def _build_task_state_snapshot(task: TaskExecution) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for raw_line in task.context.splitlines():
        match = _match_context_kv_line(raw_line)
        if match is None:
            continue
        key, value = match
        snapshot.setdefault(key, value)

    return snapshot


def _match_context_kv_line(text: str) -> tuple[str, str] | None:
    match = text.strip()
    kv_match = re.match(r".*\[KV\s+([A-Za-z][A-Za-z0-9_.]*)\]\s*(.+)", match)
    if kv_match is None:
        return None
    key = kv_match.group(1).strip()
    value = kv_match.group(2).strip()
    if not key or not value:
        return None
    return key, value
