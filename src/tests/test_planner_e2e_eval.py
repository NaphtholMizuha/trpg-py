from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from augury.agent.evals import (
    CaseExpectation,
    EvalCase,
    EvalSuite,
    evaluate_case_result,
    extract_step_signatures,
    load_eval_suite,
    load_eval_state,
    run_eval_case,
    summarize_eval_results,
    write_eval_logs,
)


class PlannerE2EEvalHelperTests(unittest.TestCase):
    def test_load_eval_suite_reads_default_fixture_bundle(self) -> None:
        suite = load_eval_suite("examples/evals/planner_e2e/cases.json")

        self.assertEqual("planner_e2e_default", suite.suite_name)
        self.assertTrue(suite.world_state_file.name.endswith("world_state.toml"))
        self.assertEqual(10, len(suite.cases))
        self.assertEqual("01_aldera_longsword_goblin_1", suite.cases[0].case_id)
        self.assertEqual("needs_human", suite.cases[8].expectation.expected_workflow_status)

    def test_load_eval_state_reads_toml_fixture(self) -> None:
        state = load_eval_state("examples/evals/planner_e2e/world_state.toml")

        self.assertIn("actors", state)
        self.assertIn("aldera", state["actors"])

    def test_extract_step_signatures_returns_type_kind_pairs(self) -> None:
        task_document = {
            "steps": [
                {"type": "select", "kind": "area"},
                {"type": "check", "kind": "save"},
                {"type": "damage", "kind": "apply"},
            ]
        }

        self.assertEqual(
            ["select.area", "check.save", "damage.apply"],
            extract_step_signatures(task_document),
        )

    def test_run_eval_case_marks_expected_ready_case_as_pass(self) -> None:
        suite = EvalSuite(
            suite_name="demo",
            world_state_file=Path("/tmp/world_state.toml"),
            default_dice=[15, 6],
            cases=[],
        )
        case = EvalCase(
            case_id="demo_case",
            instruction="Aldera用长剑攻击goblin_1",
            expectation=suite_case_expectation(
                workflow_status="ready",
                lint_status="valid",
                execution_status="success",
                changed_paths=["actors.goblin_1.hp.current"],
                step_signatures=["check.attack", "damage.apply"],
            ),
        )

        payload = run_eval_case(
            case,
            suite=suite,
            initial_state={
                "actors": {
                    "aldera": {
                        "id": "aldera",
                        "position": {"x": 0, "y": 0},
                        "attacks": {"longsword": {"to_hit": 7, "reach": 5, "damage": [{"dice": "1d8", "bonus": 4, "damage_type": "slashing"}]}},
                    },
                    "goblin_1": {
                        "id": "goblin_1",
                        "position": {"x": 0, "y": 1},
                        "hp": {"current": 7, "max": 7},
                        "ac": {"total": 13},
                    },
                }
            },
            config_path="config/config.toml",
        )

        self.assertTrue(payload["evaluation"]["passed"])
        self.assertEqual("success", payload["execution_result"]["status"])
        self.assertIn("check.attack", payload["step_signatures"])

    def test_run_eval_case_marks_unexpected_changed_paths_as_failure(self) -> None:
        suite = EvalSuite(
            suite_name="demo",
            world_state_file=Path("/tmp/world_state.toml"),
            default_dice=[4, 4, 4],
            cases=[],
        )
        case = EvalCase(
            case_id="demo_case",
            instruction="demo instruction",
            expectation=suite_case_expectation(
                workflow_status="ready",
                changed_paths=["actors.malik.hp.current"],
            ),
        )

        payload = {
            "workflow_result": {"status": "ready"},
            "execution_result": {"status": "success"},
            "step_signatures": [],
            "state_changes": [{"path": "actors.goblin_1.hp.current"}],
            "missing_info": [],
        }
        payload["evaluation"] = evaluate_case_result(case, payload)

        self.assertFalse(payload["evaluation"]["passed"])
        self.assertIn("changed_paths", payload["evaluation"]["failure_reasons"][0])

    def test_summarize_eval_results_counts_pass_and_fail(self) -> None:
        results = [
            {
                "case_id": "pass_case",
                "instruction": "pass",
                "workflow_result": {"status": "ready"},
                "execution_result": {"status": "success"},
                "evaluation": {"passed": True, "failure_reasons": []},
                "log_file": "/tmp/pass_case.json",
            },
            {
                "case_id": "fail_case",
                "instruction": "fail",
                "workflow_result": {"status": "needs_human"},
                "execution_result": {"status": "skipped"},
                "evaluation": {"passed": False, "failure_reasons": ["workflow_status mismatch"]},
                "log_file": "/tmp/fail_case.json",
            },
        ]

        summary = summarize_eval_results(results)

        self.assertEqual(2, summary["total"])
        self.assertEqual(1, summary["passed"])
        self.assertEqual(1, summary["failed"])
        self.assertEqual("fail_case", summary["results"][1]["case_id"])

    def test_write_eval_logs_persists_case_logs_and_summary(self) -> None:
        results = [
            {
                "case_id": "demo_case",
                "instruction": "demo",
                "evaluation": {"passed": True, "failure_reasons": []},
                "workflow_result": {"status": "ready"},
                "execution_result": {"status": "success"},
            }
        ]
        summary = {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "results": [
                {
                    "case_id": "demo_case",
                    "instruction": "demo",
                    "passed": True,
                    "workflow_status": "ready",
                    "execution_status": "success",
                    "failure_reasons": [],
                    "log_file": None,
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            written = write_eval_logs(results, log_dir=temp_dir, summary=summary)

            case_log = Path(temp_dir) / "demo_case.json"
            summary_log = Path(temp_dir) / "summary.json"

            self.assertTrue(case_log.exists())
            self.assertTrue(summary_log.exists())
            self.assertEqual(str(summary_log), written["summary_file"])
            self.assertEqual("demo_case", json.loads(case_log.read_text(encoding="utf-8"))["case_id"])
            self.assertEqual(1, json.loads(summary_log.read_text(encoding="utf-8"))["passed"])


def suite_case_expectation(
    *,
    workflow_status: str | None = None,
    lint_status: str | None = None,
    execution_status: str | None = None,
    changed_paths: list[str] | None = None,
    step_signatures: list[str] | None = None,
):
    return CaseExpectation(
        expected_workflow_status=workflow_status,
        expected_lint_status=lint_status,
        expected_execution_status=execution_status,
        expected_changed_paths=list(changed_paths or []),
        expected_step_signatures=list(step_signatures or []),
    )
