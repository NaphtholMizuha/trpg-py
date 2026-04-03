from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from loguru import logger
from smoke import test_dsl, test_grep, test_linter, test_reads, test_search, test_task
from augury.planner.task_document import TaskDraft
from augury.planner.tools import create_lint_tool, create_template_tool


class FakeSearcher:
    def search(
        self,
        query: str,
        *,
        mode: str = "balanced",
        limit: int,
        fetch_k: int,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            model_dump=lambda exclude_none=True: {
                "status": "ok",
                "hits": [
                    {
                        "rank": 1,
                        "score": 0.91,
                        "text": f"rule snippet for {query} [{mode}]",
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


def run_grep_script(*args: str) -> tuple[str, dict[str, object]]:
    buffer = io.StringIO()
    payload: dict[str, object] = {}
    with patch("sys.argv", ["test_grep.py", *args]):
        with redirect_stdout(buffer):
            raise_code = test_grep.main()
    if raise_code not in (None, 0):
        raise AssertionError(f"grep smoke script returned unexpected code: {raise_code}")
    if "--json" in args:
        payload = json.loads(buffer.getvalue())
    return buffer.getvalue(), payload


def build_fake_task_draft(*, instruction: str) -> TaskDraft:
    return TaskDraft(
        instruction=instruction,
        normalized_instruction=instruction,
        task="先确认哪些对象位于火球爆炸半径内，再对每个受影响对象结算敏捷豁免与火焰伤害。",
        reads=[
            "actors.aldera.spell_dc",
            "actors.aldera.spell_slots.level_3.current",
            "actors.aldera.position.x",
            "actors.goblin_1.position.x",
            "actors.goblin_1.abilities.dex.save",
            "actors.goblin_1.hp.current",
        ],
        judgments=[
            "先根据位置与爆炸范围确认哪些对象位于火球术覆盖范围内。",
            "goblin_1 makes a Dexterity saving throw against Aldera's spell DC.",
        ],
        writes=["actors.aldera.spell_slots.level_3.current", "actors.goblin_1.hp.current"],
        missing_info=["若未明确爆点，仍需确认火球爆炸中心位置。"],
        assumptions=[],
        evidence=["火球术：20尺半径范围，敏捷豁免，失败全伤，成功半伤"],
        states=[
            "actors.aldera.spell_slots.level_3.current = 2",
            "actors.aldera.position.x = 5",
            "actors.goblin_1.position.x = 4",
            "actors.goblin_1.abilities.dex.save = 2",
            "actors.goblin_1.hp.current = 7",
        ],
    )


def run_task_script(*args: str) -> tuple[str, dict[str, object]]:
    buffer = io.StringIO()
    payload: dict[str, object] = {}

    class FakeTaskNode:
        def run(self, instruction: str) -> TaskDraft:
            return build_fake_task_draft(instruction=instruction)

    def fake_build_task_node(*, state: object, config_path: object) -> FakeTaskNode:  # type: ignore[no-untyped-def]
        return FakeTaskNode()

    with patch("smoke.test_task.build_task_node", new=fake_build_task_node):
        with patch("sys.argv", ["test_task.py", *args]):
            with redirect_stdout(buffer):
                raise_code = test_task.main()
    if raise_code not in (None, 0):
        raise AssertionError(f"task smoke script returned unexpected code: {raise_code}")
    if "--json" in args:
        payload = json.loads(buffer.getvalue())
    return buffer.getvalue(), payload


def build_fake_task_document() -> dict[str, object]:
    return {
        "task_id": "planner.resolve-fireball-vs-goblin",
        "version": 1,
        "policy": {},
        "context": {
            "instruction": "Aldera用火球术攻击goblin",
            "task_draft": build_fake_task_draft(instruction="Aldera用火球术攻击goblin").model_dump(),
        },
        "steps": [
            {
                "id": "consume_slot",
                "type": "state",
                "kind": "set",
                "args": {"path": "actors.aldera.spell_slots.level_3.current", "value": 1},
            }
        ],
    }


def build_fake_lint_result() -> dict[str, object]:
    return {
        "status": "valid",
        "summary": "task document is executable",
        "issues": [],
        "dsl_node_meta": {"lint_calls": 2, "max_tool_calls": 5, "used_fallback": False},
    }


def build_fake_invalid_lint_result() -> dict[str, object]:
    return {
        "status": "invalid",
        "summary": "task document still has issues",
        "issues": [
            {
                "path": "steps.0",
                "message": "missing dice",
                "expected": {
                    "step_type": "check",
                    "step_kind": "save",
                    "required_args": ["dice", "ability"],
                    "canonical_example": {
                        "id": "dexterity_save",
                        "type": "check",
                        "kind": "save",
                        "args": {
                            "dice": "1d20",
                            "ability": "dexterity",
                            "dc_path": "actors.aldera.spell_dc",
                        },
                    },
                },
            }
        ],
        "dsl_node_meta": {"lint_calls": 1, "max_tool_calls": 5, "used_fallback": True},
    }


def build_fake_execution_result() -> dict[str, object]:
    return {
        "status": "success",
        "reason": None,
        "report": {
            "task_id": "planner.resolve-fireball-vs-goblin",
            "status": "success",
            "step_reports": [],
            "results": {},
            "applied_changes": [
                {
                    "path": "actors.aldera.spell_slots.level_3.current",
                    "old_value": 2,
                    "new_value": 1,
                    "mode": "set",
                }
            ],
            "error": None,
        },
        "state_changes": [
            {
                "path": "actors.aldera.spell_slots.level_3.current",
                "old_value": 2,
                "new_value": 1,
            }
        ],
    }


def run_dsl_script(*args: str) -> tuple[str, dict[str, object]]:
    buffer = io.StringIO()
    payload: dict[str, object] = {}
    use_real_draft = "--draft-file" in args

    def fake_run(self, draft: TaskDraft) -> tuple[dict[str, object], dict[str, object]]:  # type: ignore[no-untyped-def]
        return build_fake_task_document(), build_fake_lint_result()

    def fake_load_task_draft(path: str | Path) -> TaskDraft:  # type: ignore[no-untyped-def]
        candidate = Path(path)
        if use_real_draft and candidate.exists():
            return TaskDraft.model_validate(json.loads(candidate.read_text(encoding="utf-8")))
        return build_fake_task_draft(instruction="Aldera用火球术攻击goblin")

    with patch("smoke.test_dsl.DslNode.run", new=fake_run):
        with patch("smoke.test_dsl.load_task_draft", new=fake_load_task_draft):
            with patch("smoke.test_dsl.resolve_state_file", return_value=Path("/tmp/world_state.toml")):
                with patch("smoke.test_dsl.build_execution_result", return_value=build_fake_execution_result()):
                    with patch("sys.argv", ["test_dsl.py", *args]):
                        with redirect_stdout(buffer):
                            raise_code = test_dsl.main()
    if raise_code not in (None, 0):
        raise AssertionError(f"dsl smoke script returned unexpected code: {raise_code}")
    if "--json" in args:
        payload = json.loads(buffer.getvalue())
    return buffer.getvalue(), payload


def run_dsl_script_with_invalid_lint(*args: str) -> tuple[str, dict[str, object]]:
    buffer = io.StringIO()
    payload: dict[str, object] = {}
    use_real_draft = "--draft-file" in args

    def fake_run(self, draft: TaskDraft) -> tuple[dict[str, object], dict[str, object]]:  # type: ignore[no-untyped-def]
        return build_fake_task_document(), build_fake_invalid_lint_result()

    def fake_load_task_draft(path: str | Path) -> TaskDraft:  # type: ignore[no-untyped-def]
        candidate = Path(path)
        if use_real_draft and candidate.exists():
            return TaskDraft.model_validate(json.loads(candidate.read_text(encoding="utf-8")))
        return build_fake_task_draft(instruction="Aldera用火球术攻击goblin")

    with patch("smoke.test_dsl.DslNode.run", new=fake_run):
        with patch("smoke.test_dsl.load_task_draft", new=fake_load_task_draft):
            with patch("smoke.test_dsl.resolve_state_file", return_value=Path("/tmp/world_state.toml")):
                with patch("smoke.test_dsl.execute_generated_task") as execute_mock:
                    with patch("sys.argv", ["test_dsl.py", *args]):
                        with redirect_stdout(buffer):
                            raise_code = test_dsl.main()
                execute_mock.assert_not_called()
    if raise_code not in (None, 0):
        raise AssertionError(f"dsl smoke script returned unexpected code: {raise_code}")
    if "--json" in args:
        payload = json.loads(buffer.getvalue())
    return buffer.getvalue(), payload


class SmokeSearchScriptTests(unittest.TestCase):
    def test_search_smoke_script_supports_json_output(self) -> None:
        payload = run_search_script("--json", "fireball spell")

        self.assertEqual("ok", payload["status"])
        self.assertEqual("Fireball", payload["hits"][0]["metadata"]["title"])

    def test_search_smoke_script_supports_mode_argument(self) -> None:
        payload = run_search_script("--json", "--mode", "term", "火球术 Fireball")

        self.assertEqual("ok", payload["status"])
        self.assertIn("[term]", payload["hits"][0]["text"])

    def test_search_smoke_script_keeps_fireball_balanced_query_anchor(self) -> None:
        query = "火球术 Fireball：目标进行什么豁免，伤害如何结算，成功时是否减半"
        payload = run_search_script("--json", "--mode", "balanced", query)

        self.assertEqual("ok", payload["status"])
        self.assertIn(query, payload["hits"][0]["text"])
        self.assertIn("[balanced]", payload["hits"][0]["text"])

    def test_search_smoke_script_supports_semantic_rule_queries(self) -> None:
        query = "一个范围法术要求目标进行敏捷豁免，失败受到火焰伤害，成功伤害减半"
        payload = run_search_script("--json", "--mode", "semantic", query)

        self.assertEqual("ok", payload["status"])
        self.assertIn(query, payload["hits"][0]["text"])
        self.assertIn("[semantic]", payload["hits"][0]["text"])


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
        self.assertTrue(payload["no_match"]["suggestions"])

    def test_reads_smoke_script_prints_human_summary(self) -> None:
        output, _ = run_reads_script()

        self.assertIn("TRPG Agent Read Smoke Test", output)
        self.assertIn("match demo :", output)
        self.assertIn("no_match demo:", output)
        self.assertIn("status     : ok", output)
        self.assertIn("status     : no_match", output)
        self.assertIn("suggestions:", output)


class SmokeGrepScriptTests(unittest.TestCase):
    def test_grep_smoke_script_supports_json_output(self) -> None:
        _, payload = run_grep_script("--json")

        self.assertEqual("ok", payload["match"]["status"])
        self.assertEqual("no_match", payload["no_match"]["status"])
        self.assertTrue(payload["match"]["matches"])
        self.assertIn("key", payload["match"]["matches"][0])
        self.assertIn("value", payload["match"]["matches"][0])
        self.assertIn("sim", payload["match"]["matches"][0])

    def test_grep_smoke_script_prints_human_summary(self) -> None:
        output, _ = run_grep_script()

        self.assertIn("TRPG Agent Grep Smoke Test", output)
        self.assertIn("match demo :", output)
        self.assertIn("status     : ok", output)
        self.assertIn("status     : no_match", output)
        self.assertIn("(sim=", output)


class SmokeTaskScriptTests(unittest.TestCase):
    def test_task_smoke_script_supports_json_output(self) -> None:
        _, payload = run_task_script("--json", "--instruction", "Aldera用火球术攻击goblin")

        self.assertEqual("Aldera用火球术攻击goblin", payload["instruction"])
        self.assertEqual("先确认哪些对象位于火球爆炸半径内，再对每个受影响对象结算敏捷豁免与火焰伤害。", payload["task"])
        self.assertEqual(
            [
                "actors.aldera.spell_dc",
                "actors.aldera.spell_slots.level_3.current",
                "actors.aldera.position.x",
                "actors.goblin_1.position.x",
                "actors.goblin_1.abilities.dex.save",
                "actors.goblin_1.hp.current",
            ],
            payload["reads"],
        )
        self.assertEqual(["actors.aldera.spell_slots.level_3.current", "actors.goblin_1.hp.current"], payload["writes"])
        self.assertIn("judgments", payload)
        self.assertIn("missing_info", payload)
        self.assertEqual(["火球术：20尺半径范围，敏捷豁免，失败全伤，成功半伤"], payload["evidence"])
        self.assertEqual(
            [
                "actors.aldera.spell_slots.level_3.current = 2",
                "actors.aldera.position.x = 5",
                "actors.goblin_1.position.x = 4",
                "actors.goblin_1.abilities.dex.save = 2",
                "actors.goblin_1.hp.current = 7",
            ],
            payload["states"],
        )
        self.assertIn("爆点", payload["missing_info"][0])
        self.assertNotIn("read_values", payload)
        self.assertNotIn("context_lines", payload)

    def test_task_smoke_script_prints_human_summary(self) -> None:
        output, _ = run_task_script("--instruction", "Aldera用火球术攻击goblin")

        self.assertIn("TRPG Planner TaskNode Smoke Test", output)
        self.assertIn("instruction : Aldera用火球术攻击goblin", output)
        self.assertIn("task        : 先确认哪些对象位于火球爆炸半径内，再对每个受影响对象结算敏捷豁免与火焰伤害。", output)
        self.assertIn("reads       : 6", output)
        self.assertIn("judgments   : 2", output)
        self.assertIn("writes      : 2", output)
        self.assertIn("evidence    : 1", output)
        self.assertIn("states      : 5", output)

    def test_task_smoke_script_saves_task_draft_to_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            with patch("smoke.test_task.DEFAULT_OUTPUT_DIR", output_dir):
                _, payload = run_task_script("--json", "--instruction", "Aldera用火球术攻击goblin")

            canonical_path = output_dir / "task_draft.json"
            snapshot_path = output_dir / "task_draft_aldera用火球术攻击goblin.json"

            self.assertTrue(canonical_path.exists())
            self.assertTrue(snapshot_path.exists())
            self.assertEqual(payload, json.loads(canonical_path.read_text(encoding="utf-8")))
            self.assertEqual(payload, json.loads(snapshot_path.read_text(encoding="utf-8")))


class SmokeDslScriptTests(unittest.TestCase):
    def test_build_dsl_node_includes_template_and_lint_tools(self) -> None:
        node = test_dsl.build_dsl_node(config_path=Path("config/config.toml"))

        self.assertEqual(["template", "lint"], [tool.name for tool in node.tools])

    def test_template_and_lint_tools_emit_observable_logs(self) -> None:
        stderr = io.StringIO()
        template_tool = create_template_tool()
        lint_tool = create_lint_tool()
        task_document = {
            "task_id": "planner.tool-log-demo",
            "version": 1,
            "policy": {},
            "context": {},
            "steps": [
                {
                    "id": "record_state",
                    "type": "state",
                    "kind": "set",
                    "args": {"path": "actors.aldera.ac", "value": 18},
                }
            ],
        }

        sink_id = logger.add(stderr, format="{message}")
        try:
            template_tool.invoke(
                {
                    "task_family": "area_spell",
                    "resolution_mode": "save_damage",
                    "resource_mode": "spell_slot",
                    "targeting_mode": "center_on_target_position",
                    "success_rule": "half",
                }
            )
            template_tool.invoke(
                {
                    "task_family": "area spell or area effect",
                    "resolution_mode": "save_damage",
                    "resource_mode": "spell_slot",
                    "targeting_mode": "center_on_target_position",
                    "success_rule": "half",
                }
            )
            lint_tool.invoke({"task_document": task_document})
        finally:
            logger.remove(sink_id)

        output = stderr.getvalue()

        self.assertIn("tool_input tool=template", output)
        self.assertIn("tool_output tool=template", output)
        self.assertIn("status=error", output)
        self.assertIn("invalid_fields=['task_family']", output)
        self.assertIn("tool_input tool=lint", output)
        self.assertIn("tool_output tool=lint", output)

    def test_dsl_smoke_script_supports_json_output(self) -> None:
        _, payload = run_dsl_script("--json")

        self.assertEqual("Aldera用火球术攻击goblin", payload["draft"]["instruction"])
        self.assertEqual("planner.resolve-fireball-vs-goblin", payload["task_document"]["task_id"])
        self.assertEqual("valid", payload["lint_result"]["status"])
        self.assertEqual("success", payload["execution_result"]["status"])
        self.assertEqual("/tmp/world_state.toml", payload["state_file"])
        self.assertEqual("actors.aldera.spell_slots.level_3.current", payload["state_changes"][0]["path"])
        self.assertEqual(2, payload["lint_result"]["dsl_node_meta"]["lint_calls"])
        self.assertFalse(payload["lint_result"]["dsl_node_meta"]["used_fallback"])
        self.assertIn("steps", payload["task_document"])

    def test_dsl_smoke_script_prints_human_summary(self) -> None:
        output, _ = run_dsl_script()

        self.assertIn("TRPG Planner DslNode Smoke Test", output)
        self.assertIn("instruction : Aldera用火球术攻击goblin", output)
        self.assertIn("task_id     : planner.resolve-fireball-vs-goblin", output)
        self.assertIn("lint_status : valid", output)
        self.assertIn("lint_calls  : 2", output)
        self.assertIn("used_fallback: no", output)
        self.assertIn("execution_status : success", output)
        self.assertIn("state_changes:", output)
        self.assertIn("actors.aldera.spell_slots.level_3.current: 2 -> 1", output)
        self.assertIn("task_document:", output)
        self.assertIn("lint_result:", output)
        self.assertIn("execution_result:", output)

    def test_dsl_smoke_script_supports_custom_draft_file(self) -> None:
        custom_draft = build_fake_task_draft(instruction="Malik用长剑攻击Aldera")

        with tempfile.TemporaryDirectory() as temp_dir:
            draft_path = Path(temp_dir) / "custom_task_draft.json"
            draft_path.write_text(
                json.dumps(custom_draft.model_dump(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            _, payload = run_dsl_script("--json", "--draft-file", str(draft_path))

        self.assertEqual("Malik用长剑攻击Aldera", payload["draft"]["instruction"])
        self.assertEqual("planner.resolve-fireball-vs-goblin", payload["task_document"]["task_id"])

    def test_dsl_smoke_script_skips_execution_when_lint_is_invalid(self) -> None:
        output, payload = run_dsl_script_with_invalid_lint("--json")

        self.assertEqual("invalid", payload["lint_result"]["status"])
        self.assertEqual("skipped", payload["execution_result"]["status"])
        self.assertEqual("lint_invalid", payload["execution_result"]["reason"])
        self.assertEqual([], payload["state_changes"])
        self.assertEqual("save", payload["lint_result"]["issues"][0]["expected"]["step_kind"])
        self.assertEqual("1d20", payload["lint_result"]["issues"][0]["expected"]["canonical_example"]["args"]["dice"])
        self.assertTrue(payload["lint_result"]["dsl_node_meta"]["used_fallback"])
        self.assertIn('"status": "skipped"', output)
