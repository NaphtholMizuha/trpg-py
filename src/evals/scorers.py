"""评测打分与判定。"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from ..types import ExecutionResult, ResolutionResult, ResolutionWindow, TaskExecution
from ..utils.kv_patch import KVPatch
from .models import (
    EvalCaseResult,
    EvalFailure,
    ExecutorEvalCase,
    PlannerEvalCase,
    ResolverEvalCase,
    WorkflowEvalCase,
    WorkflowEvalOutcome,
)


def _failure(code: str, message: str) -> EvalFailure:
    return EvalFailure(code=code, message=message)


def _serialize_artifact(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _extract_context_keys(text: str) -> list[str]:
    if not text:
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    matches = re.findall(r"\[KV\s+([A-Za-z][A-Za-z0-9_.]*)\]", text)
    matches.extend(re.findall(r"\[KV\]\s*([A-Za-z][A-Za-z0-9_.]*)\s*:", text))
    for key in matches:
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def _extract_root_key(path: str) -> str | None:
    parts = path.split(".")
    if len(parts) < 3:
        return None
    return ".".join(parts[:2])


def _path_is_field_level(path: str) -> bool:
    return _extract_root_key(path) is not None


def score_planner_case(
    case: PlannerEvalCase,
    task: TaskExecution,
    *,
    duration_ms: float = 0.0,
) -> EvalCaseResult:
    """对 planner case 打分。"""
    failures: list[EvalFailure] = []

    if not task.task_id.strip():
        failures.append(_failure("planner.task_id_missing", "Planner 输出缺少 task_id。"))
    if not task.description.strip():
        failures.append(_failure("planner.description_missing", "Planner 输出缺少 description。"))
    if not task.context.strip():
        failures.append(_failure("planner.context_missing", "Planner 输出缺少 context。"))

    if case.expect.actor is not None and task.actor != case.expect.actor:
        failures.append(
            _failure(
                "planner.actor_mismatch",
                f"期望 actor={case.expect.actor}，实际为 {task.actor!r}。",
            )
        )

    if case.expect.target is not None and task.target != case.expect.target:
        failures.append(
            _failure(
                "planner.target_mismatch",
                f"期望 target={case.expect.target}，实际为 {task.target!r}。",
            )
        )

    missing_targets = [
        target
        for target in case.expect.must_include_write_targets
        if target not in (task.write_targets or [])
    ]
    if missing_targets:
        failures.append(
            _failure(
                "planner.write_targets_missing",
                f"缺少预期 write_targets: {', '.join(missing_targets)}。",
            )
        )

    invalid_targets = [path for path in (task.write_targets or []) if not _path_is_field_level(path)]
    if invalid_targets:
        failures.append(
            _failure(
                "planner.write_targets_invalid",
                f"write_targets 中存在非字段级路径: {', '.join(invalid_targets)}。",
            )
        )

    if case.expect.must_not_require_dm_confirmation and "[Needs Confirmation]" in task.context:
        failures.append(
            _failure(
                "planner.unexpected_dm_confirmation",
                "case 要求无需 DM 二次确认，但 context 中仍包含 [Needs Confirmation]。",
            )
        )

    matched_targets = len(case.expect.must_include_write_targets) - len(missing_targets)
    total_expected = len(case.expect.must_include_write_targets)
    soft_scores = {
        "write_target_coverage": (matched_targets / total_expected) if total_expected else 1.0,
        "has_actor": 1.0 if task.actor else 0.0,
        "has_target": 1.0 if task.target else 0.0,
    }

    return EvalCaseResult(
        case_id=case.case_id,
        case_type="planner",
        passed=not failures,
        duration_ms=duration_ms,
        failures=failures,
        soft_scores=soft_scores,
        artifacts={"task": _serialize_artifact(task)},
    )


def score_executor_case(
    case: ExecutorEvalCase,
    result: ExecutionResult,
    *,
    duration_ms: float = 0.0,
) -> EvalCaseResult:
    """对 executor case 打分。"""
    failures: list[EvalFailure] = []
    touched_paths = [change.path for change in result.field_changes]

    if case.expect.success is not None and result.success is not case.expect.success:
        failures.append(
            _failure(
                "executor.success_mismatch",
                f"期望 success={case.expect.success}，实际为 {result.success}。",
            )
        )

    invalid_paths = [path for path in touched_paths if not _path_is_field_level(path)]
    if invalid_paths:
        failures.append(
            _failure(
                "executor.invalid_path",
                f"存在非字段级路径: {', '.join(invalid_paths)}。",
            )
        )

    missing_paths = [path for path in case.expect.must_touch_paths if path not in touched_paths]
    if missing_paths:
        failures.append(
            _failure(
                "executor.must_touch_paths_missing",
                f"缺少预期写回路径: {', '.join(missing_paths)}。",
            )
        )

    if not case.expect.allow_narration_only and not result.field_changes:
        failures.append(
            _failure(
                "executor.narration_only_not_allowed",
                "当前 case 不允许 narration-only 结果，但未产出 field_changes。",
            )
        )

    if case.expect.must_not_touch_unknown_keys:
        allowed_roots = set(_extract_context_keys(case.task.context))
        unknown_paths = [
            path
            for path in touched_paths
            if (root_key := _extract_root_key(path)) is None or root_key not in allowed_roots
        ]
        if unknown_paths:
            failures.append(
                _failure(
                    "executor.unknown_path",
                    f"写回了上下文中未出现的路径: {', '.join(unknown_paths)}。",
                )
            )

    matched_paths = len(case.expect.must_touch_paths) - len(missing_paths)
    total_expected = len(case.expect.must_touch_paths)
    soft_scores = {
        "path_coverage": (matched_paths / total_expected) if total_expected else 1.0,
        "has_narration": 1.0 if (result.narration or "").strip() else 0.0,
    }

    return EvalCaseResult(
        case_id=case.case_id,
        case_type="executor",
        passed=not failures,
        duration_ms=duration_ms,
        failures=failures,
        soft_scores=soft_scores,
        artifacts={"result": _serialize_artifact(result)},
    )


def score_resolver_case(
    case: ResolverEvalCase,
    result: ResolutionResult,
    *,
    duration_ms: float = 0.0,
) -> EvalCaseResult:
    """对 resolver case 打分。"""
    failures: list[EvalFailure] = []
    final_paths = [change.path for change in result.final_field_changes]
    discarded_paths = [change.path for change in result.discarded_field_changes]

    invalid_final_paths = [path for path in final_paths if not _path_is_field_level(path)]
    invalid_discarded_paths = [path for path in discarded_paths if not _path_is_field_level(path)]
    if invalid_final_paths or invalid_discarded_paths:
        failures.append(
            _failure(
                "resolver.invalid_path",
                "resolver 输出中存在非字段级路径。",
            )
        )

    missing_final_paths = [path for path in case.expect.final_paths if path not in final_paths]
    if missing_final_paths:
        failures.append(
            _failure(
                "resolver.final_paths_missing",
                f"缺少预期 final paths: {', '.join(missing_final_paths)}。",
            )
        )

    missing_discarded_paths = [
        path
        for path in case.expect.discarded_paths
        if path not in discarded_paths
    ]
    if missing_discarded_paths:
        failures.append(
            _failure(
                "resolver.discarded_paths_missing",
                f"缺少预期 discarded paths: {', '.join(missing_discarded_paths)}。",
                )
            )

    resolved_state = _materialize_window_state(case.window, result)
    mismatched_final_values = []
    for path, expected_value in case.expect.expected_final_values.items():
        actual_value = resolved_state.get(path)
        if actual_value != expected_value:
            mismatched_final_values.append((path, expected_value, actual_value))
    if mismatched_final_values:
        failures.append(
            _failure(
                "resolver.final_state_mismatch",
                "最终状态不符合预期: "
                + "; ".join(
                    f"{path} 期望 {expected!r}，实际 {actual!r}"
                    for path, expected, actual in mismatched_final_values
                ),
            )
        )

    if case.expect.must_not_emit_unknown_paths:
        allowed_paths = _collect_allowed_paths(case.window)
        unknown_paths = [
            path
            for path in [*final_paths, *discarded_paths]
            if allowed_paths and path not in allowed_paths
        ]
        if unknown_paths:
            failures.append(
                _failure(
                    "resolver.unknown_path",
                    f"resolver 输出了窗口中未出现的 path: {', '.join(unknown_paths)}。",
                )
            )

    matched_final_paths = len(case.expect.final_paths) - len(missing_final_paths)
    total_final = len(case.expect.final_paths)
    matched_discarded_paths = len(case.expect.discarded_paths) - len(missing_discarded_paths)
    total_discarded = len(case.expect.discarded_paths)
    matched_final_values = len(case.expect.expected_final_values) - len(mismatched_final_values)
    total_final_values = len(case.expect.expected_final_values)
    soft_scores = {
        "final_path_coverage": (matched_final_paths / total_final) if total_final else 1.0,
        "discarded_path_coverage": (
            (matched_discarded_paths / total_discarded) if total_discarded else 1.0
        ),
        "final_state_coverage": (
            (matched_final_values / total_final_values) if total_final_values else 1.0
        ),
        "has_resolution_summary": 1.0 if (result.resolution_summary or "").strip() else 0.0,
    }

    return EvalCaseResult(
        case_id=case.case_id,
        case_type="resolver",
        passed=not failures,
        duration_ms=duration_ms,
        failures=failures,
        soft_scores=soft_scores,
        artifacts={
            "result": _serialize_artifact(result),
            "resolved_state": resolved_state,
        },
    )


def score_workflow_case(
    case: WorkflowEvalCase,
    outcome: WorkflowEvalOutcome,
    *,
    duration_ms: float = 0.0,
) -> EvalCaseResult:
    """对 workflow case 打分。

    当前 workflow eval 只根据最终 KV state 是否符合预期来判定。
    中间过程轨迹保留在 artifacts 中，但不再影响 pass / fail。
    """
    failures: list[EvalFailure] = []

    mismatched_final_values = []
    for path, expected_value in case.expect.expected_final_values.items():
        actual_value = outcome.final_state.get(path)
        if actual_value != expected_value:
            mismatched_final_values.append((path, expected_value, actual_value))
    if mismatched_final_values:
        failures.append(
            _failure(
                "workflow.final_state_mismatch",
                "最终状态不符合预期: "
                + "; ".join(
                    f"{path} 期望 {expected!r}，实际 {actual!r}"
                    for path, expected, actual in mismatched_final_values
                ),
            )
        )

    behavior_failures = []
    for path, behavior in case.expect.expected_field_behaviors.items():
        initial_value = outcome.initial_state.get(path)
        final_value = outcome.final_state.get(path)
        if not _field_behavior_matches(initial_value, final_value, behavior):
            behavior_failures.append((path, behavior, initial_value, final_value))
    if behavior_failures:
        failures.append(
            _failure(
                "workflow.field_behavior_mismatch",
                "字段变化不符合预期: "
                + "; ".join(
                    f"{path} 期望 {behavior}，初始 {initial!r}，最终 {final!r}"
                    for path, behavior, initial, final in behavior_failures
                ),
            )
        )

    total_final_values = len(case.expect.expected_final_values)
    total_behaviors = len(case.expect.expected_field_behaviors)
    soft_scores = {
        "final_value_coverage": (
            (total_final_values - len(mismatched_final_values)) / total_final_values
            if total_final_values
            else 1.0
        ),
        "field_behavior_coverage": (
            (total_behaviors - len(behavior_failures)) / total_behaviors
            if total_behaviors
            else 1.0
        ),
        "finished": 1.0 if outcome.finished else 0.0,
        "active_window_cleared": 0.0 if outcome.active_window_present else 1.0,
    }

    return EvalCaseResult(
        case_id=case.case_id,
        case_type="workflow",
        passed=not failures,
        duration_ms=duration_ms,
        failures=failures,
        soft_scores=soft_scores,
        artifacts={"workflow": _serialize_artifact(outcome)},
    )


def _collect_allowed_paths(window: ResolutionWindow) -> set[str]:
    allowed_paths: set[str] = set()
    for run in window.runs:
        for change in run.field_changes:
            if change.path:
                allowed_paths.add(change.path)
    return allowed_paths


def _materialize_window_state(
    window: ResolutionWindow,
    result: ResolutionResult,
) -> dict[str, str | None]:
    state = dict(window.state_snapshot or {})
    for change in result.final_field_changes:
        root_key = _extract_root_key(change.path)
        if not root_key:
            continue
        field = change.path.split(".")[-1]
        current_full = state.get(root_key, "")
        patch = KVPatch(current_full or "")
        if change.operation.value == "DEL":
            patch.remove_field(field)
        else:
            patch.set_field(field, change.new_value or "")
        state[root_key] = patch.to_string()

    flattened: dict[str, str | None] = {}
    for root_key, full_value in state.items():
        patch = KVPatch(full_value or "")
        for field, value in patch.fields.items():
            flattened[f"{root_key}.{field}"] = value
    return flattened


def _field_behavior_matches(
    initial_value: str | None,
    final_value: str | None,
    behavior: str,
) -> bool:
    if behavior == "changed":
        return initial_value != final_value
    if behavior == "unchanged":
        return initial_value == final_value

    initial_number = _coerce_numeric_value(initial_value)
    final_number = _coerce_numeric_value(final_value)
    if initial_number is None or final_number is None:
        return False
    if behavior == "increased":
        return final_number > initial_number
    if behavior == "decreased":
        return final_number < initial_number
    return False


def _coerce_numeric_value(value: str | None) -> float | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    hp_match = re.match(r"(-?\d+)\s*/\s*(-?\d+)", stripped)
    if hp_match:
        return float(hp_match.group(1))
    number_match = re.match(r"-?\d+(?:\.\d+)?", stripped)
    if number_match:
        return float(number_match.group(0))
    return None
