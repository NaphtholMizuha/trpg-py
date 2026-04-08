from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from augury.agent.runtime import PlannerDependencies, create_planner
from augury.agent.state_loader import load_toml_state
from augury.agent.tools.search_stub import create_search_stub_tool
from augury.engine.core.dice import FixedDiceRoller


@dataclass(slots=True)
class CaseExpectation:
    expected_workflow_status: str | None = None
    expected_step_signatures: list[str] = field(default_factory=list)
    expected_lint_status: str | None = None
    expected_execution_status: str | None = None
    expected_changed_paths: list[str] = field(default_factory=list)
    expected_missing_info_contains: list[str] = field(default_factory=list)


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


def run_eval_case(
    case: EvalCase,
    *,
    suite: EvalSuite,
    initial_state: dict[str, Any],
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    state = deepcopy(initial_state)
    planner = create_planner(
        state=state,
        dependencies=PlannerDependencies(search_tool=create_search_stub_tool()),
        config_path=str(config_path) if config_path is not None else None,
        roller=FixedDiceRoller(list(case.dice or suite.default_dice)),
    )
    result = planner.invoke(case.instruction)
    payload = {
        "case_id": case.case_id,
        "instruction": case.instruction,
        "description": case.description,
        "tags": list(case.tags),
        "workflow_result": result.model_dump(),
        "task_document": result.task_document,
        "step_signatures": extract_step_signatures(result.task_document),
        "lint_result": result.lint_result,
        "execution_result": _build_execution_result(result),
        "state_changes": list(result.state_changes),
        "missing_info": list(result.missing_info),
    }
    payload["evaluation"] = evaluate_case_result(case, payload)
    return payload


def evaluate_case_result(case: EvalCase, payload: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failure_reasons: list[str] = []
    expectation = case.expectation

    workflow_result = payload.get("workflow_result") or {}
    lint_result = payload.get("lint_result") or {}
    execution_result = payload.get("execution_result") or {}
    step_signatures = payload.get("step_signatures") or []
    state_changes = payload.get("state_changes") or []
    missing_info = payload.get("missing_info") or []

    _check_equal(checks, failure_reasons, "workflow_status", workflow_result.get("status"), expectation.expected_workflow_status)
    _check_equal(checks, failure_reasons, "lint_status", lint_result.get("status"), expectation.expected_lint_status)
    _check_equal(checks, failure_reasons, "execution_status", execution_result.get("status"), expectation.expected_execution_status)
    _check_subset(checks, failure_reasons, "step_signatures", list(step_signatures), expectation.expected_step_signatures)
    changed_paths = [str(change.get("path")) for change in state_changes if isinstance(change, dict)]
    _check_subset(checks, failure_reasons, "changed_paths", changed_paths, expectation.expected_changed_paths)
    _check_contains_all(checks, failure_reasons, "missing_info_contains", list(missing_info), expectation.expected_missing_info_contains)
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
    return {"total": len(results), "passed": passed, "failed": len(results) - passed, "results": items}


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
        {**item, "log_file": str(resolved_log_dir / f"{item['case_id']}.json")}
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


def _build_execution_result(result: Any) -> dict[str, Any]:
    if result.execution_report is None:
        return {"status": "skipped"}
    report_status = result.execution_report.get("status") if isinstance(result.execution_report, dict) else None
    return {"status": report_status or "unknown", "report": result.execution_report}


def _coerce_case(raw_case: Any) -> EvalCase:
    expectation = raw_case.get("expectation", {}) if isinstance(raw_case, dict) else {}
    return EvalCase(
        case_id=str(raw_case["case_id"]),
        instruction=str(raw_case["instruction"]),
        description=str(raw_case.get("description", "")),
        tags=[str(tag) for tag in raw_case.get("tags", [])],
        dice=[int(value) for value in raw_case.get("dice", [])],
        expectation=CaseExpectation(
            expected_workflow_status=expectation.get("expected_workflow_status"),
            expected_step_signatures=list(expectation.get("expected_step_signatures", [])),
            expected_lint_status=expectation.get("expected_lint_status"),
            expected_execution_status=expectation.get("expected_execution_status"),
            expected_changed_paths=list(expectation.get("expected_changed_paths", [])),
            expected_missing_info_contains=list(expectation.get("expected_missing_info_contains", [])),
        ),
    )


def _check_equal(
    checks: list[dict[str, Any]],
    failure_reasons: list[str],
    name: str,
    actual: Any,
    expected: Any,
) -> None:
    if expected is None:
        return
    passed = actual == expected
    checks.append({"name": name, "passed": passed, "actual": actual, "expected": expected})
    if not passed:
        failure_reasons.append(f"{name} mismatch: expected {expected!r}, got {actual!r}")


def _check_subset(
    checks: list[dict[str, Any]],
    failure_reasons: list[str],
    name: str,
    actual: list[str],
    expected: list[str],
) -> None:
    if not expected:
        return
    missing = [item for item in expected if item not in actual]
    checks.append({"name": name, "passed": not missing, "actual": actual, "expected": expected})
    if missing:
        failure_reasons.append(f"{name} missing expected items: {missing}")


def _check_contains_all(
    checks: list[dict[str, Any]],
    failure_reasons: list[str],
    name: str,
    actual: list[str],
    expected: list[str],
) -> None:
    if not expected:
        return
    missing = [item for item in expected if not any(item in candidate for candidate in actual)]
    checks.append({"name": name, "passed": not missing, "actual": actual, "expected": expected})
    if missing:
        failure_reasons.append(f"{name} missing expected fragments: {missing}")
