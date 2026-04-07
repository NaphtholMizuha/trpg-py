from __future__ import annotations

import json
import traceback
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from augury import FixedDiceRoller, execute_task
from augury.planner import PlannerWorkflow, PlannerWorkflowDependencies
from augury.planner.nodes import DslNode, DslNodeDependencies, TaskNode, TaskNodeDependencies
from augury.planner.tools import (
    create_grep_tool,
    create_lint_tool,
    create_search_tool,
    create_template_tool,
)
from smoke.execution_helpers import summarize_state_changes
from smoke.state_loader import load_toml_state


@dataclass(slots=True)
class CaseExpectation:
    expected_workflow_status: str | None = None
    expected_missing_info_contains: list[str] = field(default_factory=list)
    expected_read_paths: list[str] = field(default_factory=list)
    expected_write_paths: list[str] = field(default_factory=list)
    expected_step_signatures: list[str] = field(default_factory=list)
    expected_lint_status: str | None = None
    expected_execution_status: str | None = None
    expected_changed_paths: list[str] = field(default_factory=list)
    expected_unchanged_paths: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EvalCase:
    case_id: str
    instruction: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    dice: list[int] = field(default_factory=list)
    expectation: CaseExpectation = field(default_factory=CaseExpectation)


@dataclass(slots=True)
class EvalSuite:
    suite_name: str
    world_state_file: Path
    default_dice: list[int] = field(default_factory=list)
    cases: list[EvalCase] = field(default_factory=list)


def load_eval_suite(path: str | Path) -> EvalSuite:
    suite_path = Path(path).expanduser().resolve()
    payload = json.loads(suite_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("eval suite file must contain a JSON object at the root")
    world_state_file = (suite_path.parent / str(payload["world_state_file"])).resolve()
    cases = [_coerce_case(item) for item in payload.get("cases", [])]
    return EvalSuite(
        suite_name=str(payload.get("suite_name", suite_path.stem)),
        world_state_file=world_state_file,
        default_dice=[int(value) for value in payload.get("default_dice", [])],
        cases=cases,
    )


def load_eval_state(path: str | Path) -> dict[str, Any]:
    return load_toml_state(path)


def build_eval_workflow(*, state: dict[str, Any], config_path: str | Path) -> PlannerWorkflow:
    return PlannerWorkflow(
        state=state,
        dependencies=PlannerWorkflowDependencies(
            task_node=TaskNode(
                TaskNodeDependencies(
                    grep_tool=create_grep_tool(state=state),
                    search_tool=create_search_tool(config_path=str(config_path)),
                    config_path=config_path,
                )
            ),
            dsl_node=DslNode(
                DslNodeDependencies(
                    template_tool=create_template_tool(),
                    lint_tool=create_lint_tool(),
                    config_path=config_path,
                )
            ),
        ),
    )


def build_case_roller(case: EvalCase, suite: EvalSuite) -> FixedDiceRoller:
    values = case.dice or suite.default_dice
    return FixedDiceRoller(list(values))


def run_eval_case(
    case: EvalCase,
    *,
    suite: EvalSuite,
    initial_state: dict[str, Any],
    config_path: str | Path,
) -> dict[str, Any]:
    state = deepcopy(initial_state)
    payload: dict[str, Any] = {
        "case_id": case.case_id,
        "instruction": case.instruction,
        "description": case.description,
        "tags": list(case.tags),
        "initial_state_file": str(suite.world_state_file),
        "dice": list(case.dice or suite.default_dice),
        "workflow_result": None,
        "draft": None,
        "missing_info": [],
        "task_document": None,
        "step_signatures": [],
        "lint_result": None,
        "execution_result": None,
        "state_changes": [],
    }

    try:
        workflow = build_eval_workflow(state=state, config_path=config_path)
        workflow_result = workflow.invoke(case.instruction)
        workflow_dump = workflow_result.model_dump()
        task_document = workflow_dump.get("task_document")
        lint_result = workflow_dump.get("lint_result")
        payload.update(
            {
                "workflow_result": workflow_dump,
                "draft": workflow_dump.get("draft"),
                "missing_info": workflow_dump.get("missing_info", []),
                "task_document": task_document,
                "step_signatures": extract_step_signatures(task_document),
                "lint_result": lint_result,
                "execution_result": None,
                "state_changes": [],
            }
        )
        execution_result = _build_execution_result(
            workflow_status=workflow_result.status,
            task_document=task_document,
            lint_result=lint_result,
            state=state,
            roller=build_case_roller(case, suite),
        )
        payload["execution_result"] = execution_result
        payload["state_changes"] = execution_result.get("state_changes", [])
    except Exception as exc:
        stage = "execution" if payload.get("workflow_result") is not None else "workflow"
        payload.update(
            {
                "error": {
                    "stage": stage,
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                },
            }
        )
    payload["evaluation"] = evaluate_case_result(case, payload)
    return payload


def evaluate_case_result(case: EvalCase, payload: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failure_reasons: list[str] = []
    expectation = case.expectation

    if payload.get("error"):
        failure_reasons.append(f"workflow error: {payload['error']['type']}")
        return {"passed": False, "checks": checks, "failure_reasons": failure_reasons}

    workflow_result = payload.get("workflow_result") or {}
    draft = payload.get("draft") or {}
    lint_result = payload.get("lint_result") or {}
    execution_result = payload.get("execution_result") or {}
    state_changes = payload.get("state_changes") or []
    step_signatures = payload.get("step_signatures") or []
    missing_info = payload.get("missing_info") or []

    _check_equal(
        checks,
        failure_reasons,
        "workflow_status",
        workflow_result.get("status"),
        expectation.expected_workflow_status,
    )
    _check_equal(
        checks,
        failure_reasons,
        "lint_status",
        lint_result.get("status"),
        expectation.expected_lint_status,
    )
    _check_equal(
        checks,
        failure_reasons,
        "execution_status",
        execution_result.get("status"),
        expectation.expected_execution_status,
    )
    _check_contains_all(
        checks,
        failure_reasons,
        "missing_info_contains",
        list(missing_info),
        expectation.expected_missing_info_contains,
    )
    _check_subset(
        checks,
        failure_reasons,
        "read_paths",
        list(draft.get("reads", [])) if isinstance(draft, dict) else [],
        expectation.expected_read_paths,
    )
    _check_subset(
        checks,
        failure_reasons,
        "write_paths",
        list(draft.get("writes", [])) if isinstance(draft, dict) else [],
        expectation.expected_write_paths,
    )
    _check_subset(
        checks,
        failure_reasons,
        "step_signatures",
        list(step_signatures),
        expectation.expected_step_signatures,
    )
    changed_paths = [str(change.get("path")) for change in state_changes if isinstance(change, dict)]
    _check_subset(
        checks,
        failure_reasons,
        "changed_paths",
        changed_paths,
        expectation.expected_changed_paths,
    )
    _check_absent(
        checks,
        failure_reasons,
        "unchanged_paths",
        changed_paths,
        expectation.expected_unchanged_paths,
    )
    return {"passed": not failure_reasons, "checks": checks, "failure_reasons": failure_reasons}


def summarize_eval_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    passed = 0
    for result in results:
        evaluation = result.get("evaluation") or {}
        case_passed = bool(evaluation.get("passed"))
        if case_passed:
            passed += 1
        workflow_result = result.get("workflow_result") or {}
        execution_result = result.get("execution_result") or {}
        items.append(
            {
                "case_id": result.get("case_id"),
                "instruction": result.get("instruction"),
                "passed": case_passed,
                "workflow_status": workflow_result.get("status"),
                "execution_status": execution_result.get("status"),
                "failure_reasons": list(evaluation.get("failure_reasons", [])),
                "log_file": result.get("log_file"),
            }
        )
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": items,
    }


def write_eval_logs(
    results: list[dict[str, Any]],
    *,
    log_dir: str | Path,
    summary: dict[str, Any],
) -> dict[str, Any]:
    resolved_log_dir = Path(log_dir).expanduser().resolve()
    resolved_log_dir.mkdir(parents=True, exist_ok=True)
    written_results: list[dict[str, Any]] = []
    for result in results:
        payload = dict(result)
        log_path = resolved_log_dir / f"{result['case_id']}.json"
        log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        payload["log_file"] = str(log_path)
        written_results.append(payload)
    summary_payload = dict(summary)
    summary_payload["results"] = [
        {
            **item,
            "log_file": str(resolved_log_dir / f"{item['case_id']}.json"),
        }
        for item in summary.get("results", [])
    ]
    summary_path = resolved_log_dir / "summary.json"
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "log_dir": str(resolved_log_dir),
        "summary_file": str(summary_path),
        "results": written_results,
        "summary": summary_payload,
    }


def extract_step_signatures(task_document: dict[str, Any] | None) -> list[str]:
    if not isinstance(task_document, dict):
        return []
    signatures: list[str] = []
    for step in task_document.get("steps", []):
        if not isinstance(step, dict):
            continue
        step_type = step.get("type")
        step_kind = step.get("kind")
        if isinstance(step_type, str) and isinstance(step_kind, str):
            signatures.append(f"{step_type}.{step_kind}")
    return signatures


def _coerce_case(raw_case: Any) -> EvalCase:
    if not isinstance(raw_case, dict):
        raise ValueError("each case entry must be an object")
    expectation = raw_case.get("expectation", {})
    if not isinstance(expectation, dict):
        raise ValueError("case expectation must be an object")
    return EvalCase(
        case_id=str(raw_case["case_id"]),
        instruction=str(raw_case["instruction"]),
        description=str(raw_case.get("description", "")),
        tags=[str(tag) for tag in raw_case.get("tags", [])],
        dice=[int(value) for value in raw_case.get("dice", [])],
        expectation=CaseExpectation(
            expected_workflow_status=_optional_str(expectation.get("expected_workflow_status")),
            expected_missing_info_contains=[str(item) for item in expectation.get("expected_missing_info_contains", [])],
            expected_read_paths=[str(item) for item in expectation.get("expected_read_paths", [])],
            expected_write_paths=[str(item) for item in expectation.get("expected_write_paths", [])],
            expected_step_signatures=[str(item) for item in expectation.get("expected_step_signatures", [])],
            expected_lint_status=_optional_str(expectation.get("expected_lint_status")),
            expected_execution_status=_optional_str(expectation.get("expected_execution_status")),
            expected_changed_paths=[str(item) for item in expectation.get("expected_changed_paths", [])],
            expected_unchanged_paths=[str(item) for item in expectation.get("expected_unchanged_paths", [])],
        ),
    )


def _optional_str(value: Any) -> str | None:
    return str(value) if isinstance(value, str) and value else None


def _build_execution_result(
    *,
    workflow_status: str,
    task_document: dict[str, Any] | None,
    lint_result: dict[str, Any] | None,
    state: dict[str, Any],
    roller: FixedDiceRoller,
) -> dict[str, Any]:
    if workflow_status != "ready":
        return {"status": "skipped", "reason": "workflow_not_ready", "report": None, "state_changes": []}
    if task_document is None:
        return {"status": "skipped", "reason": "missing_task_document", "report": None, "state_changes": []}
    if lint_result is None or lint_result.get("status") != "valid":
        return {"status": "skipped", "reason": "lint_invalid", "report": None, "state_changes": []}

    initial_state = deepcopy(state)
    report = execute_task(task_document, state, roller=roller)
    return {
        "status": report.status,
        "reason": None,
        "report": report.to_dict(),
        "state_changes": summarize_state_changes(initial_state, state),
    }


def _check_equal(
    checks: list[dict[str, Any]],
    failures: list[str],
    name: str,
    actual: Any,
    expected: Any,
) -> None:
    if expected is None:
        return
    passed = actual == expected
    checks.append({"name": name, "passed": passed, "expected": expected, "actual": actual})
    if not passed:
        failures.append(f"{name}: expected {expected!r}, got {actual!r}")


def _check_subset(
    checks: list[dict[str, Any]],
    failures: list[str],
    name: str,
    actual_items: list[str],
    expected_items: list[str],
) -> None:
    if not expected_items:
        return
    missing = [item for item in expected_items if item not in actual_items]
    passed = not missing
    checks.append({"name": name, "passed": passed, "expected": expected_items, "actual": actual_items})
    if missing:
        failures.append(f"{name}: missing expected items {missing!r}")


def _check_contains_all(
    checks: list[dict[str, Any]],
    failures: list[str],
    name: str,
    actual_items: list[str],
    expected_needles: list[str],
) -> None:
    if not expected_needles:
        return
    missing: list[str] = []
    haystack = "\n".join(actual_items)
    for needle in expected_needles:
        if needle not in haystack:
            missing.append(needle)
    passed = not missing
    checks.append({"name": name, "passed": passed, "expected": expected_needles, "actual": actual_items})
    if missing:
        failures.append(f"{name}: missing substrings {missing!r}")


def _check_absent(
    checks: list[dict[str, Any]],
    failures: list[str],
    name: str,
    actual_items: list[str],
    forbidden_items: list[str],
) -> None:
    if not forbidden_items:
        return
    present = [item for item in forbidden_items if item in actual_items]
    passed = not present
    checks.append({"name": name, "passed": passed, "expected_absent": forbidden_items, "actual": actual_items})
    if present:
        failures.append(f"{name}: expected items to stay unchanged but found {present!r}")


__all__ = [
    "CaseExpectation",
    "EvalCase",
    "EvalSuite",
    "build_case_roller",
    "build_eval_workflow",
    "evaluate_case_result",
    "extract_step_signatures",
    "load_eval_state",
    "load_eval_suite",
    "run_eval_case",
    "summarize_eval_results",
    "write_eval_logs",
]
