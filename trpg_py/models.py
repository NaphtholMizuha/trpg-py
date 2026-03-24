from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class TaskStep:
    id: str
    type: str
    kind: str
    args: dict[str, Any]
    tags: list[str] = field(default_factory=list)
    when: Any = None


@dataclass(slots=True)
class TaskDocument:
    task_id: str
    version: int
    policy: dict[str, Any]
    context: dict[str, Any]
    steps: list[TaskStep]


@dataclass(slots=True)
class ChangeInstruction:
    path: str
    value: Any
    mode: str = "set"


@dataclass(slots=True)
class AppliedChange:
    path: str
    old_value: Any
    new_value: Any
    mode: str = "set"


@dataclass(slots=True)
class OperationResult:
    outputs: dict[str, Any] = field(default_factory=dict)
    changes: list[ChangeInstruction] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class StepReport:
    id: str
    type: str
    kind: str
    status: str
    outputs: dict[str, Any] = field(default_factory=dict)
    changes: list[AppliedChange] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


@dataclass(slots=True)
class ExecutionReport:
    task_id: str
    status: str
    step_reports: list[StepReport] = field(default_factory=list)
    results: dict[str, Any] = field(default_factory=dict)
    applied_changes: list[AppliedChange] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
