"""评测模型定义。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..types import ExecutionResult, ResolutionResult, ResolutionWindow, TaskExecution

EvalCaseType = Literal["planner", "executor", "resolver", "workflow"]


class PlannerExpectation(BaseModel):
    """Planner case 的预期。"""

    model_config = ConfigDict(extra="forbid")

    actor: str | None = None
    target: str | None = None
    must_include_write_targets: list[str] = Field(default_factory=list)
    must_not_require_dm_confirmation: bool = False


class ExecutorExpectation(BaseModel):
    """Executor case 的预期。"""

    model_config = ConfigDict(extra="forbid")

    success: bool | None = None
    must_touch_paths: list[str] = Field(default_factory=list)
    must_not_touch_unknown_keys: bool = False
    allow_narration_only: bool = True


class ResolverExpectation(BaseModel):
    """Resolver case 的预期。"""

    model_config = ConfigDict(extra="forbid")

    final_paths: list[str] = Field(default_factory=list)
    discarded_paths: list[str] = Field(default_factory=list)
    expected_final_values: dict[str, str] = Field(default_factory=dict)
    must_not_emit_unknown_paths: bool = False


class WorkflowTaskExpectation(BaseModel):
    """Workflow 中 planner 产出 task 的预期。"""

    model_config = ConfigDict(extra="forbid")

    description_contains: str | None = None
    actor: str | None = None
    target: str | None = None
    must_include_write_targets: list[str] = Field(default_factory=list)


class WorkflowExecutionExpectation(BaseModel):
    """Workflow 中 executor 中间结果的预期。"""

    model_config = ConfigDict(extra="forbid")

    description_contains: str | None = None
    success: bool | None = None
    must_touch_paths: list[str] = Field(default_factory=list)
    allow_narration_only: bool = True


class WorkflowWindowExpectation(BaseModel):
    """Workflow 中结算窗口轨迹的预期。"""

    model_config = ConfigDict(extra="forbid")

    root_description_contains: str | None = None
    min_run_count: int = 1


class WorkflowExpectation(BaseModel):
    """Workflow case 的预期。"""

    model_config = ConfigDict(extra="forbid")

    expected_final_values: dict[str, str] = Field(default_factory=dict)
    expected_field_behaviors: dict[
        str,
        Literal["changed", "unchanged", "increased", "decreased"],
    ] = Field(default_factory=dict)
    task_sequence: list[WorkflowTaskExpectation] = Field(default_factory=list)
    execution_sequence: list[WorkflowExecutionExpectation] = Field(default_factory=list)
    window_sequence: list[WorkflowWindowExpectation] = Field(default_factory=list)
    interrupt_sequence: list[str] = Field(default_factory=list)
    must_finish: bool = True
    must_clear_active_window: bool = True


class WorkflowInterruptScriptStep(BaseModel):
    """Workflow interrupt 脚本。"""

    model_config = ConfigDict(extra="forbid")

    type: str
    resume: dict[str, Any] = Field(default_factory=dict)


class PlannerEvalCase(BaseModel):
    """Planner 评测 case。"""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    input: str
    expect: PlannerExpectation
    tags: list[str] = Field(default_factory=list)


class ExecutorEvalCase(BaseModel):
    """Executor 评测 case。"""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    task: TaskExecution
    expect: ExecutorExpectation
    tags: list[str] = Field(default_factory=list)


class ResolverEvalCase(BaseModel):
    """Resolver 评测 case。"""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    window: ResolutionWindow
    expect: ResolverExpectation
    tags: list[str] = Field(default_factory=list)


class WorkflowEvalCase(BaseModel):
    """Workflow 评测 case。"""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    user_input: str
    interrupt_script: list[WorkflowInterruptScriptStep] = Field(default_factory=list)
    expect: WorkflowExpectation
    world_state_path: str | None = None
    max_loops: int = 20
    tags: list[str] = Field(default_factory=list)


class WorkflowTaskTrace(BaseModel):
    """Workflow 中记录的 task 轨迹。"""

    model_config = ConfigDict(extra="forbid")

    task_id: str = ""
    description: str
    actor: str | None = None
    target: str | None = None
    write_targets: list[str] = Field(default_factory=list)


class WorkflowExecutionTrace(BaseModel):
    """Workflow 中记录的 execution 轨迹。"""

    model_config = ConfigDict(extra="forbid")

    task_id: str = ""
    description: str
    success: bool = False
    touched_paths: list[str] = Field(default_factory=list)
    narration: str = ""


class WorkflowWindowTrace(BaseModel):
    """Workflow 中记录的窗口轨迹。"""

    model_config = ConfigDict(extra="forbid")

    window_id: str
    root_description: str
    run_count: int = 0


class WorkflowInterruptTrace(BaseModel):
    """Workflow 中记录的 interrupt 轨迹。"""

    model_config = ConfigDict(extra="forbid")

    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowEvalOutcome(BaseModel):
    """Workflow runner 输出的结构化结果。"""

    model_config = ConfigDict(extra="forbid")

    finished: bool = False
    active_window_present: bool = False
    initial_state: dict[str, str] = Field(default_factory=dict)
    final_state: dict[str, str] = Field(default_factory=dict)
    tasks: list[WorkflowTaskTrace] = Field(default_factory=list)
    executions: list[WorkflowExecutionTrace] = Field(default_factory=list)
    windows: list[WorkflowWindowTrace] = Field(default_factory=list)
    interrupts: list[WorkflowInterruptTrace] = Field(default_factory=list)
    script_mismatches: list[str] = Field(default_factory=list)
    unused_script_steps: int = 0
    exception: str | None = None


class EvalFailure(BaseModel):
    """单条评测失败信息。"""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class EvalCaseResult(BaseModel):
    """单个 case 的评测结果。"""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    case_type: EvalCaseType
    passed: bool
    duration_ms: float = 0.0
    failures: list[EvalFailure] = Field(default_factory=list)
    soft_scores: dict[str, float] = Field(default_factory=dict)
    artifacts: dict[str, Any] = Field(default_factory=dict)


class EvalReport(BaseModel):
    """某一类 case 的聚合报告。"""

    model_config = ConfigDict(extra="forbid")

    case_type: EvalCaseType
    generated_at: str
    provider: str = ""
    model: str = ""
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    results: list[EvalCaseResult] = Field(default_factory=list)

    @classmethod
    def from_results(
        cls,
        *,
        case_type: EvalCaseType,
        results: list[EvalCaseResult],
        provider: str = "",
        model: str = "",
    ) -> "EvalReport":
        total_cases = len(results)
        passed_cases = sum(1 for result in results if result.passed)
        failed_cases = total_cases - passed_cases
        pass_rate = (passed_cases / total_cases) if total_cases else 0.0
        return cls(
            case_type=case_type,
            generated_at=datetime.now(timezone.utc).isoformat(),
            provider=provider,
            model=model,
            total_cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            pass_rate=pass_rate,
            results=results,
        )


CaseModel = PlannerEvalCase | ExecutorEvalCase | ResolverEvalCase | WorkflowEvalCase
