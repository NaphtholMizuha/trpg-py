"""
核心类型定义。
"""
from typing import TypedDict, Annotated, Any, Literal
from enum import Enum

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Operation(Enum):
    """状态变更操作。"""

    ADD = "ADD"
    MOD = "MOD"
    DEL = "DEL"


class StateChange(BaseModel):
    """统一的状态变更记录。"""

    model_config = ConfigDict(extra="forbid")

    path: str
    old_value: str | None = None
    new_value: str | None = None
    operation: Operation
    source: str = ""


class TaskExecution(BaseModel):
    """Planner 输出并在工作流中流转的单步任务。"""

    model_config = ConfigDict(extra="forbid")

    task_id: str = ""
    description: str
    context: str
    action_type: Literal["攻击", "施法", "移动", "检定", "交互", "自定义"] = "自定义"
    raw_query_appendix: list[str] = Field(default_factory=list)
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

        for field_name in (
            "execution_steps",
            "write_targets",
            "raw_query_appendix",
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

        field_changes = normalized.get("field_changes")
        if field_changes is None or field_changes == {}:
            normalized["field_changes"] = []
        elif isinstance(field_changes, dict):
            normalized["field_changes"] = [field_changes]

        triggered_chains = normalized.get("triggered_chains")
        if triggered_chains is None or triggered_chains == {}:
            normalized["triggered_chains"] = []
        elif isinstance(triggered_chains, dict):
            normalized["triggered_chains"] = [triggered_chains]

        if normalized.get("narration") is None:
            normalized["narration"] = ""

        return normalized


class AgentState(TypedDict):
    """LangGraph Agent 状态。"""

    messages: Annotated[list[BaseMessage], add_messages]
    changes: Annotated[list[StateChange], lambda x, y: x + y]
    task_queue: list[TaskExecution]
    _current_task: TaskExecution | None
    _planned_message_count: int
    _execution_result: ExecutionResult | None
