from __future__ import annotations

import io
import json
import tempfile
import unittest
from copy import deepcopy
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from smoke import test_linter, test_planner, test_planner_engine, test_reads, test_search
from tests.config_helpers import write_project_config
from trpg_py.config import DEFAULT_PROJECT_CONFIG_PATH


class FakeSearcher:
    def search(self, query: str, *, limit: int, fetch_k: int) -> SimpleNamespace:
        return SimpleNamespace(
            model_dump=lambda exclude_none=True: {
                "status": "ok",
                "hits": [
                    {
                        "rank": 1,
                        "score": 0.91,
                        "text": f"rule snippet for {query}",
                        "metadata": {"title": "Fireball", "file": "phb"},
                    }
                ],
            }
        )


def run_search_script(*args: str) -> dict[str, object]:
    buffer = io.StringIO()
    with patch("smoke.test_search.build_default_searcher", return_value=FakeSearcher()):
        with patch("sys.argv", ["test_search.py", *args]):
            with redirect_stdout(buffer):
                raise_code = test_search.main()
    if raise_code not in (None, 0):
        raise AssertionError(f"search smoke script returned unexpected code: {raise_code}")
    return json.loads(buffer.getvalue())


def run_linter_script(*args: str) -> tuple[str, dict[str, object]]:
    buffer = io.StringIO()
    payload: dict[str, object] = {}
    with patch("sys.argv", ["test_linter.py", *args]):
        with redirect_stdout(buffer):
            raise_code = test_linter.main()
    if raise_code not in (None, 0):
        raise AssertionError(f"linter smoke script returned unexpected code: {raise_code}")
    if "--json" in args:
        payload = json.loads(buffer.getvalue())
    return buffer.getvalue(), payload


def run_reads_script(*args: str) -> tuple[str, dict[str, object]]:
    buffer = io.StringIO()
    payload: dict[str, object] = {}
    with patch("sys.argv", ["test_reads.py", *args]):
        with redirect_stdout(buffer):
            raise_code = test_reads.main()
    if raise_code not in (None, 0):
        raise AssertionError(f"reads smoke script returned unexpected code: {raise_code}")
    if "--json" in args:
        payload = json.loads(buffer.getvalue())
    return buffer.getvalue(), payload


class FakePlanner:
    def __init__(self, *, payload: dict[str, object] | list[dict[str, object]] | None = None, error: Exception | None = None) -> None:
        if isinstance(payload, list):
            self.payloads = list(payload)
        else:
            self.payloads = [payload or {}]
        self.error = error
        self.calls: list[object] = []

    def plan(self, request: object) -> SimpleNamespace:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        if not self.payloads:
            raise AssertionError("No fake planner payloads remaining")
        next_payload = self.payloads.pop(0)
        return SimpleNamespace(model_dump=lambda exclude_none=True: next_payload)


class FakeExecutionReport:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def to_dict(self) -> dict[str, object]:
        return self.payload


def run_planner_script(
    *args: str,
    planner_payload: dict[str, object] | list[dict[str, object]] | None = None,
    planner_error: Exception | None = None,
    create_error: Exception | None = None,
    planner_log_path: str | None = None,
    user_inputs: list[str] | None = None,
) -> tuple[str, dict[str, object]]:
    buffer = io.StringIO()
    captured: dict[str, object] = {}
    created: dict[str, object] = {}

    def fake_create_planner(**kwargs: object) -> FakePlanner:
        captured.update(kwargs)
        if create_error is not None:
            raise create_error
        planner = FakePlanner(payload=planner_payload, error=planner_error)
        if planner_log_path is not None:
            planner.last_run_log_path = planner_log_path
        created["planner"] = planner
        return planner

    with patch("smoke.test_planner.create_planner", side_effect=fake_create_planner):
        with patch("sys.argv", ["test_planner.py", *args]):
            with patch("builtins.input", side_effect=list(user_inputs or [])):
                with redirect_stdout(buffer):
                    raise_code = test_planner.main()
    if raise_code not in (None, 0):
        raise AssertionError(f"planner smoke script returned unexpected code: {raise_code}")
    if "planner" in created:
        captured["planner"] = created["planner"]
    return buffer.getvalue(), captured


def _default_execution_payload() -> dict[str, object]:
    return {
        "task_id": "goblin_scimitar_attack",
        "status": "success",
        "step_reports": [
            {
                "id": "attack_roll",
                "type": "check",
                "kind": "attack",
                "status": "success",
                "outputs": {
                    "outcome": "success",
                    "total": 16,
                    "natural": 12,
                    "roll_mode": "normal",
                    "chosen": 12,
                    "modifier": 4,
                    "threshold": 16,
                    "rolls": [12],
                    "target_ids": ["aldera"],
                },
            },
            {
                "id": "apply_damage",
                "type": "damage",
                "kind": "apply",
                "status": "success",
                "outputs": {
                    "per_target": {
                        "aldera": {
                            "final_total": 6,
                            "multiplier": 1,
                            "base_total": 6,
                            "components": [
                                {
                                    "dice": "1d6",
                                    "bonus": 2,
                                    "damage_type": "slashing",
                                    "rolls": [4],
                                    "total": 6,
                                }
                            ],
                        }
                    }
                },
            },
        ],
        "results": {},
        "applied_changes": [
            {
                "path": "actors.aldera.hp.current",
                "old_value": 30,
                "new_value": 24,
                "mode": "set",
            }
        ],
        "error": None,
    }


def run_planner_engine_script(
    *args: str,
    planner_payload: dict[str, object] | list[dict[str, object]] | None = None,
    planner_error: Exception | None = None,
    create_error: Exception | None = None,
    planner_log_path: str | None = None,
    execute_payload: dict[str, object] | None = None,
    execute_error: Exception | None = None,
    user_inputs: list[str] | None = None,
) -> tuple[str, dict[str, object]]:
    buffer = io.StringIO()
    captured: dict[str, object] = {}
    created: dict[str, object] = {}
    engine_calls: list[dict[str, object]] = []

    def fake_create_planner(**kwargs: object) -> FakePlanner:
        captured.update(kwargs)
        if create_error is not None:
            raise create_error
        planner = FakePlanner(payload=planner_payload, error=planner_error)
        if planner_log_path is not None:
            planner.last_run_log_path = planner_log_path
        created["planner"] = planner
        return planner

    def fake_execute_task(task_document: object, state: object, *, roller: object) -> FakeExecutionReport:
        engine_calls.append(
            {
                "task_document": deepcopy(task_document),
                "state": deepcopy(state),
                "roller": roller,
            }
        )
        if execute_error is not None:
            raise execute_error
        return FakeExecutionReport(execute_payload or _default_execution_payload())

    with patch("smoke.test_planner_engine.create_planner", side_effect=fake_create_planner):
        with patch("smoke.test_planner_engine.execute_task", side_effect=fake_execute_task):
            with patch("sys.argv", ["test_planner_engine.py", *args]):
                with patch("builtins.input", side_effect=list(user_inputs or [])):
                    with redirect_stdout(buffer):
                        raise_code = test_planner_engine.main()
    if raise_code not in (None, 0):
        raise AssertionError(f"planner+engine smoke script returned unexpected code: {raise_code}")
    if "planner" in created:
        captured["planner"] = created["planner"]
    if engine_calls:
        captured["engine_calls"] = engine_calls
    return buffer.getvalue(), captured


class SmokeSearchScriptTests(unittest.TestCase):
    def test_search_smoke_script_supports_json_output(self) -> None:
        payload = run_search_script("--json", "fireball spell")

        self.assertEqual("ok", payload["status"])
        self.assertEqual("Fireball", payload["hits"][0]["metadata"]["title"])


class SmokeLinterScriptTests(unittest.TestCase):
    def test_linter_smoke_script_supports_json_output(self) -> None:
        _, payload = run_linter_script("--json")

        self.assertEqual("valid", payload["valid"]["status"])
        self.assertEqual("invalid", payload["invalid"]["status"])
        self.assertIn("steps.0.id", [issue["path"] for issue in payload["invalid"]["issues"]])

    def test_linter_smoke_script_prints_human_summary(self) -> None:
        output, _ = run_linter_script()

        self.assertIn("TRPG Agent Lint Smoke Test", output)
        self.assertIn("valid demo :", output)
        self.assertIn("invalid demo:", output)
        self.assertIn("status     : valid", output)
        self.assertIn("status     : invalid", output)


class SmokeReadsScriptTests(unittest.TestCase):
    def test_reads_smoke_script_supports_json_output(self) -> None:
        _, payload = run_reads_script("--json")

        self.assertEqual("ok", payload["match"]["status"])
        self.assertEqual("no_match", payload["no_match"]["status"])
        self.assertEqual("aldera", payload["match"]["items"][0]["value"])

    def test_reads_smoke_script_prints_human_summary(self) -> None:
        output, _ = run_reads_script()

        self.assertIn("TRPG Agent Reads Smoke Test", output)
        self.assertIn("match demo :", output)
        self.assertIn("no_match demo:", output)
        self.assertIn("status     : ok", output)
        self.assertIn("status     : no_match", output)


class SmokePlannerScriptTests(unittest.TestCase):
    def test_planner_smoke_script_uses_real_entrypoint_defaults(self) -> None:
        output, captured = run_planner_script(
            "--json",
            planner_payload={
                "status": "ready",
                "task_document": {"task_id": "goblin_scimitar_attack", "steps": [{}]},
            },
        )
        payload = json.loads(output)

        self.assertEqual("ready", payload["status"])
        self.assertEqual("goblin_scimitar_attack", payload["task_document"]["task_id"])
        self.assertEqual(str(DEFAULT_PROJECT_CONFIG_PATH), captured["config_path"])
        self.assertIn("state", captured)
        self.assertEqual("洞穴哥布林斥候", captured["state"]["actors"]["goblin_1"]["name"])
        self.assertEqual("slashing", captured["state"]["actors"]["goblin_1"]["attacks"]["scimitar"]["damage"][0]["damage_type"])
        self.assertNotIn("search_tool", captured)
        self.assertNotIn("fetch_keys_tool", captured)
        self.assertNotIn("model_builder", captured)
        self.assertNotIn("agent_factory", captured)

    def test_planner_smoke_script_prints_lint_tool_in_human_summary(self) -> None:
        output, _ = run_planner_script(
            planner_payload={
                "status": "ready",
                "task_document": {"task_id": "goblin_scimitar_attack", "steps": [{}]},
            },
        )

        self.assertIn("tools      : search=real, fetch_keys=real, reads=real, lint=real", output)

    def test_planner_smoke_script_loads_world_state_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(
                Path(temp_dir) / "config.toml",
                planner_smoke_world_state_template=(
                    "[actors.hero_1]\n"
                    "id = \"hero_1\"\n"
                    "hp = { current = 12, max = 20 }\n"
                    "\n"
                    "[environment]\n"
                    "scene = \"测试战场\"\n"
                ),
            )

            _, captured = run_planner_script(
                "--json",
                "--config",
                str(config_path),
                planner_payload={
                    "status": "ready",
                    "task_document": {"task_id": "demo", "steps": []},
                },
            )

        self.assertEqual(12, captured["state"]["actors"]["hero_1"]["hp"]["current"])
        self.assertEqual("测试战场", captured["state"]["environment"]["scene"])

    def test_planner_smoke_script_reports_needs_human(self) -> None:
        output, _ = run_planner_script(
            "--json",
            planner_payload={
                "status": "needs_human",
                "questions": [{"question": "Which goblin?"}],
                "missing_info": ["target_id"],
            },
        )
        payload = json.loads(output)

        self.assertEqual("needs_human", payload["status"])
        self.assertEqual("target_id", payload["missing_info"][0])

    def test_planner_smoke_script_reports_blocked_when_planner_call_fails(self) -> None:
        output, _ = run_planner_script("--json", planner_error=RuntimeError("planner backend unavailable"))
        payload = json.loads(output)

        self.assertEqual("blocked", payload["status"])
        self.assertEqual("RuntimeError", payload["error"]["type"])

    def test_planner_smoke_script_reports_blocked_when_factory_fails(self) -> None:
        output, _ = run_planner_script("--json", create_error=RuntimeError("invalid config"))
        payload = json.loads(output)

        self.assertEqual("blocked", payload["status"])
        self.assertEqual("RuntimeError", payload["error"]["type"])

    def test_planner_smoke_script_passes_resume_request(self) -> None:
        output, captured = run_planner_script(
            "--json",
            "--thread-id",
            "thread-123",
            "--resume-json",
            '{"decisions": [{"type": "approve"}]}',
            planner_payload={
                "status": "ready",
                "task_document": {"task_id": "goblin_scimitar_attack", "steps": [{}]},
            },
        )
        payload = json.loads(output)

        self.assertEqual("ready", payload["status"])
        request = captured["planner"].calls[0]
        self.assertEqual("thread-123", request.thread_id)
        self.assertEqual({"decisions": [{"type": "approve"}]}, request.resume)

    def test_planner_smoke_script_prints_resume_thread_for_hitl(self) -> None:
        output, _ = run_planner_script(
            "--instruction",
            "Goblin attacks hero_1",
            planner_payload={
                "status": "needs_human",
                "questions": [{"question": "Approve the tool call?"}],
                "missing_info": ["human_review"],
                "resume": {"thread_id": "thread-hitl"},
            },
            user_inputs=["quit"],
        )

        self.assertIn("status     : needs_human", output)
        self.assertIn("resume     : thread-hitl", output)

    def test_planner_smoke_script_resumes_interactively_in_same_thread(self) -> None:
        output, captured = run_planner_script(
            planner_payload=[
                {
                    "status": "needs_human",
                    "questions": [{"question": "Approve the tool call?", "options": ["approve", "reject"]}],
                    "missing_info": ["human_review"],
                    "resume": {"thread_id": "thread-hitl"},
                },
                {
                    "status": "ready",
                    "task_document": {"task_id": "goblin_scimitar_attack", "steps": [{}]},
                },
            ],
            user_inputs=["approve"],
        )

        self.assertIn("hitl       : waiting for user input", output)
        self.assertIn("options    : approve, reject", output)
        self.assertIn("task_id    : goblin_scimitar_attack", output)
        self.assertEqual(2, len(captured["planner"].calls))
        resumed_request = captured["planner"].calls[1]
        self.assertEqual("thread-hitl", resumed_request.thread_id)
        self.assertEqual({"decisions": [{"type": "approve"}]}, resumed_request.resume)

    def test_planner_smoke_script_passes_debug_request(self) -> None:
        _, captured = run_planner_script(
            "--json",
            "--debug",
            planner_payload={
                "status": "ready",
                "task_document": {"task_id": "goblin_scimitar_attack", "steps": [{}]},
            },
        )

        request = captured["planner"].calls[0]
        self.assertTrue(request.debug)

    def test_planner_smoke_script_prints_validation_detail_without_debug(self) -> None:
        output, _ = run_planner_script(
            planner_payload={
                "status": "needs_human",
                "reason": "task_document_validation",
                "questions": [{"question": "Planner could not repair the task document."}],
                "missing_info": ["task_document_validation"],
                "error": {
                    "type": "ValidationError",
                    "message": "Step 1 references a future result that is not yet available.",
                },
            },
        )

        self.assertIn("reason     : task_document_validation", output)
        self.assertIn("error_type : ValidationError", output)
        self.assertIn("detail     : Step 1 references a future result that is not yet available.", output)

    def test_planner_smoke_script_keeps_regular_needs_human_output_compact(self) -> None:
        output, _ = run_planner_script(
            planner_payload={
                "status": "needs_human",
                "questions": [{"question": "Which goblin?"}],
                "missing_info": ["target_id"],
            },
        )

        self.assertIn("status     : needs_human", output)
        self.assertNotIn("detail     :", output)

    def test_planner_smoke_script_includes_debug_payload_in_json_output(self) -> None:
        output, _ = run_planner_script(
            "--json",
            "--debug",
            planner_payload={
                "status": "needs_human",
                "reason": "task_document_validation",
                "questions": [{"question": "Planner could not repair the task document."}],
                "missing_info": ["task_document_validation"],
                "debug": {
                    "attempts": [
                        {
                            "round": 1,
                            "input_mode": "prompt",
                            "validation_error": "Unsupported step type 'oops'",
                        }
                    ],
                    "failure_stage": "schema_or_semantic_validation",
                    "failure_message": "Unsupported step type 'oops'",
                },
            },
        )
        payload = json.loads(output)

        self.assertEqual("task_document_validation", payload["reason"])
        self.assertEqual("schema_or_semantic_validation", payload["debug"]["failure_stage"])
        self.assertEqual(1, payload["debug"]["attempts"][0]["round"])

    def test_planner_smoke_script_includes_planner_log_path_in_json_output(self) -> None:
        output, _ = run_planner_script(
            "--json",
            planner_payload={
                "status": "ready",
                "task_document": {"task_id": "goblin_scimitar_attack", "steps": [{}]},
            },
            planner_log_path="/tmp/planner/run.log",
        )
        payload = json.loads(output)

        self.assertEqual("/tmp/planner/run.log", payload["planner_log_path"])

    def test_planner_smoke_script_prints_debug_summary(self) -> None:
        output, _ = run_planner_script(
            "--debug",
            planner_payload={
                "status": "needs_human",
                "reason": "task_document_validation",
                "questions": [{"question": "Planner could not repair the task document."}],
                "missing_info": ["task_document_validation"],
                "debug": {
                    "attempts": [
                        {
                            "round": 1,
                            "input_mode": "prompt",
                            "validation_error": "Unsupported step type 'oops'",
                        }
                    ],
                    "failure_stage": "schema_or_semantic_validation",
                    "failure_message": "Unsupported step type 'oops'",
                },
            },
        )

        self.assertIn("debug      : on", output)
        self.assertIn("reason     : task_document_validation", output)
        self.assertIn("failure    : schema_or_semantic_validation", output)
        self.assertIn("detail     : Unsupported step type 'oops'", output)
        self.assertIn("debug_try  : 1", output)

    def test_planner_smoke_script_prints_log_path_summary(self) -> None:
        output, _ = run_planner_script(
            planner_payload={
                "status": "blocked",
                "error": {"type": "RuntimeError", "message": "planner backend unavailable"},
            },
            planner_log_path="/tmp/planner/run.log",
        )

        self.assertIn("log_path   : /tmp/planner/run.log", output)


class SmokePlannerEngineScriptTests(unittest.TestCase):
    def test_planner_engine_smoke_script_executes_ready_task_and_returns_json(self) -> None:
        output, captured = run_planner_engine_script(
            "--json",
            planner_payload={
                "status": "ready",
                "task_document": {"task_id": "goblin_scimitar_attack", "steps": [{}, {}]},
            },
        )
        payload = json.loads(output)

        self.assertEqual("ready", payload["planner"]["status"])
        self.assertEqual("success", payload["execution"]["report"]["status"])
        self.assertEqual([20, 4, 4, 4, 4], payload["rolls"])
        self.assertEqual("goblin_scimitar_attack", captured["engine_calls"][0]["task_document"]["task_id"])

    def test_planner_engine_smoke_script_resumes_hitl_before_execution(self) -> None:
        output, captured = run_planner_engine_script(
            planner_payload=[
                {
                    "status": "needs_human",
                    "questions": [{"question": "Approve the tool call?", "options": ["approve", "reject"]}],
                    "missing_info": ["human_review"],
                    "resume": {"thread_id": "thread-hitl"},
                },
                {
                    "status": "ready",
                    "task_document": {"task_id": "goblin_scimitar_attack", "steps": [{}]},
                },
            ],
            user_inputs=["approve"],
        )

        self.assertIn("hitl       : waiting for user input", output)
        self.assertIn("Planner Stage", output)
        self.assertIn("Execution Stage", output)
        self.assertEqual(2, len(captured["planner"].calls))
        resumed_request = captured["planner"].calls[1]
        self.assertEqual("thread-hitl", resumed_request.thread_id)
        self.assertEqual({"decisions": [{"type": "approve"}]}, resumed_request.resume)
        self.assertEqual(1, len(captured["engine_calls"]))

    def test_planner_engine_smoke_script_does_not_execute_when_planner_blocked(self) -> None:
        output, captured = run_planner_engine_script(
            planner_payload={
                "status": "blocked",
                "error": {"type": "RuntimeError", "message": "planner backend unavailable"},
            },
            planner_log_path="/tmp/planner/run.log",
        )

        self.assertIn("Planner Stage", output)
        self.assertIn("blocked", output)
        self.assertIn("/tmp/planner/run.log", output)
        self.assertNotIn("engine_calls", captured)

    def test_planner_engine_smoke_script_stops_when_tester_quits_hitl(self) -> None:
        output, captured = run_planner_engine_script(
            planner_payload={
                "status": "needs_human",
                "questions": [{"question": "Approve the tool call?"}],
                "missing_info": ["human_review"],
                "resume": {"thread_id": "thread-hitl"},
            },
            user_inputs=["quit"],
        )

        self.assertIn("hitl       : stopped by user", output)
        self.assertNotIn("engine_calls", captured)

    def test_planner_engine_smoke_script_prints_human_readable_stage_and_changes(self) -> None:
        output, _ = run_planner_engine_script(
            planner_payload={
                "status": "ready",
                "task_document": {"task_id": "goblin_scimitar_attack", "steps": [{}, {}]},
            },
        )

        self.assertIn("TRPG Planner + Engine Smoke Test", output)
        self.assertIn("Planner Stage", output)
        self.assertIn("Execution Stage", output)
        self.assertIn("Applied Changes", output)
        self.assertIn("actors.aldera.hp.current", output)

    def test_planner_engine_smoke_script_prints_critical_attack_summary(self) -> None:
        crit_execution_payload = _default_execution_payload()
        crit_execution_payload["step_reports"][0]["outputs"]["outcome"] = "crit_success"
        crit_execution_payload["step_reports"][0]["outputs"]["total"] = 24
        crit_execution_payload["step_reports"][0]["outputs"]["natural"] = 20
        crit_execution_payload["step_reports"][0]["outputs"]["chosen"] = 20
        crit_execution_payload["step_reports"][0]["outputs"]["rolls"] = [20]
        crit_execution_payload["step_reports"][1]["outputs"]["per_target"]["aldera"]["final_total"] = 10
        crit_execution_payload["step_reports"][1]["outputs"]["per_target"]["aldera"]["base_total"] = 10
        crit_execution_payload["step_reports"][1]["outputs"]["per_target"]["aldera"]["components"][0]["rolls"] = [4, 4]
        crit_execution_payload["step_reports"][1]["outputs"]["per_target"]["aldera"]["components"][0]["total"] = 10
        crit_execution_payload["applied_changes"][0]["new_value"] = 20

        output, _ = run_planner_engine_script(
            planner_payload={
                "status": "ready",
                "task_document": {"task_id": "goblin_scimitar_attack", "steps": [{}, {}]},
            },
            execute_payload=crit_execution_payload,
        )

        self.assertIn("crit_success", output)
        self.assertIn("[4, 4]", output)
        self.assertIn("actors.aldera.hp.current", output)
        self.assertIn("30 -> 20", output)
