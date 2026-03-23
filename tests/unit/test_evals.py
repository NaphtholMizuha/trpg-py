import json

from src.evals.cases import load_case_file
from src.evals.models import (
    ExecutorEvalCase,
    PlannerEvalCase,
    ResolverEvalCase,
    WorkflowEvalCase,
)
from src.evals.reporting import render_report_summary, write_report
from src.evals.runner import (
    run_executor_cases,
    run_planner_cases,
    run_resolver_cases,
    run_workflow_cases,
)
from src.types import (
    DiscardedStateChange,
    ExecutionResult,
    Operation,
    ResolutionResult,
    ResolutionWindow,
    ResolutionWindowRun,
    StateChange,
    TaskExecution,
    WindowStatus,
)


class FakePlannerAgent:
    def __init__(self, task: TaskExecution):
        self.task = task

    def plan(self, user_input: str) -> TaskExecution:
        return self.task


class FakeExecutorAgent:
    def __init__(self, result: ExecutionResult):
        self.result = result

    def execute(self, task: TaskExecution) -> ExecutionResult:
        return self.result


class FakeResolverAgent:
    def __init__(self, result: ResolutionResult):
        self.result = result

    def resolve(self, window: ResolutionWindow) -> ResolutionResult:
        return self.result


class FakeStore:
    def __init__(self, initial_state: dict[str, str], final_state: dict[str, str]):
        self._data = initial_state.copy()
        self._final_state = final_state.copy()

    def to_dict(self) -> dict[str, str]:
        return self._data.copy()

    def commit_final(self) -> None:
        self._data = self._final_state.copy()


class FakeWorkflow:
    def __init__(self, store: FakeStore, outputs_per_call: list[list[dict]]):
        self.store = store
        self.outputs_per_call = outputs_per_call
        self.calls = 0

    def stream(self, current_input, config, stream_mode="values"):
        self.calls += 1
        if self.calls == len(self.outputs_per_call):
            self.store.commit_final()
        return self.outputs_per_call[self.calls - 1]


def test_load_planner_case_file(tmp_path):
    case_path = tmp_path / "planner_case.json"
    case_path.write_text(
        json.dumps(
            {
                "case_id": "planner_demo",
                "input": "马利克对艾尔德拉施放魔法飞弹",
                "expect": {
                    "actor": "Malik",
                    "target": "Aldera",
                    "must_include_write_targets": ["Aldera.combat.HP"],
                    "must_not_require_dm_confirmation": False,
                },
                "tags": ["demo"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    case = load_case_file(case_path, "planner")

    assert isinstance(case, PlannerEvalCase)
    assert case.case_id == "planner_demo"
    assert case.expect.actor == "Malik"


def test_run_planner_cases_generates_pass_report():
    case = PlannerEvalCase.model_validate(
        {
            "case_id": "planner_magic_missile",
            "input": "马利克对艾尔德拉施放魔法飞弹",
            "expect": {
                "actor": "Malik",
                "target": "Aldera",
                "must_include_write_targets": ["Aldera.combat.HP", "Malik.spell_slots.1环"],
                "must_not_require_dm_confirmation": False,
            },
        }
    )
    task = TaskExecution(
        task_id="task_magic_missile",
        description="马利克对艾尔德拉施放魔法飞弹",
        context="[KV Aldera.combat] HP: 44/44 | AC: 18\n[KV Malik.spell_slots] 1环: 4/4",
        actor="Malik",
        target="Aldera",
        write_targets=["Aldera.combat.HP", "Malik.spell_slots.1环"],
        source="dm",
        task_category="normal",
    )

    report = run_planner_cases([case], FakePlannerAgent(task), provider="test", model="fake")

    assert report.total_cases == 1
    assert report.passed_cases == 1
    assert report.results[0].passed is True


def test_run_executor_cases_flags_unknown_paths():
    case = ExecutorEvalCase.model_validate(
        {
            "case_id": "executor_unknown_path",
            "task": {
                "task_id": "task_magic_missile",
                "description": "马利克对艾尔德拉施放魔法飞弹",
                "context": "[KV Aldera.combat] HP: 44/44 | AC: 18\n[KV Malik.spell_slots] 1环: 4/4",
                "actor": "Malik",
                "target": "Aldera",
                "write_targets": ["Aldera.combat.HP"],
                "source": "dm",
                "task_category": "normal",
            },
            "expect": {
                "success": True,
                "must_touch_paths": ["Goblin.combat.HP"],
                "must_not_touch_unknown_keys": True,
                "allow_narration_only": False,
            },
        }
    )
    result = ExecutionResult(
        task_id="task_magic_missile",
        success=True,
        field_changes=[
            StateChange(
                path="Goblin.combat.HP",
                old_value="10/10",
                new_value="3/10",
                operation=Operation.MOD,
                source="task_magic_missile",
            )
        ],
        narration="错误地打到了 Goblin。",
    )

    report = run_executor_cases([case], FakeExecutorAgent(result), provider="test", model="fake")

    assert report.failed_cases == 1
    assert report.results[0].passed is False
    assert any(failure.code == "executor.unknown_path" for failure in report.results[0].failures)


def test_run_resolver_cases_and_write_report(tmp_path):
    case = ResolverEvalCase.model_validate(
        {
            "case_id": "resolver_demo",
            "window": {
                "window_id": "window_demo",
                "root_task_id": "task_demo",
                "root_description": "demo",
                "status": "ready",
                "runs": [
                    {
                        "order": 0,
                        "priority": 10,
                        "task_id": "task_demo",
                        "description": "demo",
                        "field_changes": [
                            {
                                "path": "Aldera.combat.HP",
                                "old_value": "44/44",
                                "new_value": "35/44",
                                "operation": "MOD",
                                "source": "task_demo",
                            },
                            {
                                "path": "Aldera.spell_slots.1环",
                                "old_value": "4/4",
                                "new_value": "3/4",
                                "operation": "MOD",
                                "source": "task_shield",
                            }
                        ],
                    }
                ],
            },
            "expect": {
                "final_paths": ["Aldera.combat.HP"],
                "discarded_paths": ["Aldera.spell_slots.1环"],
                "expected_final_values": {"Aldera.combat.HP": "35/44"},
                "must_not_emit_unknown_paths": True,
            },
        }
    )
    result = ResolutionResult(
        window_id="window_demo",
        final_field_changes=[
            StateChange(
                path="Aldera.combat.HP",
                old_value="44/44",
                new_value="35/44",
                operation=Operation.MOD,
                source="resolver:window_demo",
            )
        ],
        discarded_field_changes=[
            DiscardedStateChange(
                path="Aldera.spell_slots.1环",
                old_value="4/4",
                new_value="3/4",
                operation=Operation.MOD,
                source="task_shield",
                discarded_by="resolver:window_demo",
                reason="被更高优先级动作覆盖。",
            )
        ],
        resolution_summary="resolver 完成合并。",
    )

    report = run_resolver_cases([case], FakeResolverAgent(result), provider="test", model="fake")
    report_path = write_report(report, tmp_path / "resolver-report.json")
    summary = render_report_summary(report)

    assert report.passed_cases == 1
    assert report_path.exists()
    assert "case_type: resolver" in summary
    assert report.results[0].artifacts["resolved_state"]["Aldera.combat.HP"] == "35/44"


def test_load_workflow_case_file(tmp_path):
    case_path = tmp_path / "workflow_case.json"
    case_path.write_text(
        json.dumps(
            {
                "case_id": "workflow_demo",
                "user_input": "艾尔德拉用长剑攻击哥布林",
                "interrupt_script": [
                    {"type": "task_approval", "resume": {"action": "approve"}},
                    {"type": "resolution_window_review", "resume": {"action": "close_window"}},
                ],
                "expect": {
                    "expected_field_behaviors": {"Goblin.combat.HP": "decreased"},
                    "task_sequence": [{"description_contains": "长剑", "actor": "Aldera", "target": "Goblin"}],
                    "execution_sequence": [{"description_contains": "长剑", "must_touch_paths": ["Goblin.combat.HP"], "allow_narration_only": False}],
                    "window_sequence": [{"root_description_contains": "长剑", "min_run_count": 1}],
                    "interrupt_sequence": ["task_approval", "resolution_window_review"],
                    "must_finish": True,
                    "must_clear_active_window": True
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    case = load_case_file(case_path, "workflow")

    assert isinstance(case, WorkflowEvalCase)
    assert case.case_id == "workflow_demo"
    assert case.expect.expected_field_behaviors["Goblin.combat.HP"] == "decreased"


def test_run_workflow_cases_collects_trace_and_final_state():
    case = WorkflowEvalCase.model_validate(
        {
            "case_id": "workflow_weapon_demo",
            "user_input": "艾尔德拉用长剑攻击哥布林，请结算这次命中的伤害。",
            "interrupt_script": [
                {"type": "task_approval", "resume": {"action": "approve"}},
                {"type": "resolution_window_review", "resume": {"action": "close_window"}},
            ],
            "expect": {
                "expected_field_behaviors": {"Goblin.combat.HP": "decreased"},
                "task_sequence": [
                    {
                        "description_contains": "法术反制",
                        "actor": "Malik",
                        "target": "Aldera",
                        "must_include_write_targets": ["Malik.spell_slots.3环"],
                    }
                ],
                "execution_sequence": [
                    {
                        "description_contains": "火球术",
                        "must_touch_paths": ["Aldera.combat.HP"],
                        "allow_narration_only": False,
                    }
                ],
                "window_sequence": [{"root_description_contains": "魔法飞弹", "min_run_count": 3}],
                "interrupt_sequence": ["resolution_window_review"],
                "must_finish": False,
                "must_clear_active_window": False,
            },
        }
    )

    task = TaskExecution(
        task_id="task_weapon_attack",
        description="艾尔德拉用长剑攻击哥布林",
        context="[KV Aldera.combat] HP: 44/44 | AC: 18\n[KV Goblin.combat] HP: 10/10 | AC: 10",
        actor="Aldera",
        target="Goblin",
        write_targets=["Goblin.combat.HP"],
        source="dm",
        task_category="normal",
    )
    execution = ExecutionResult(
        task_id="task_weapon_attack",
        success=True,
        field_changes=[
            StateChange(
                path="Goblin.combat.HP",
                old_value="10/10",
                new_value="4/10",
                operation=Operation.MOD,
                source="task_weapon_attack",
            )
        ],
        narration="长剑命中，地精受伤。",
    )
    window = ResolutionWindow(
        window_id="window_001",
        root_task_id="task_weapon_attack",
        root_description="艾尔德拉用长剑攻击哥布林",
        status=WindowStatus.OPEN,
        state_snapshot={"Goblin.combat": "HP: 10/10 | AC: 10"},
        runs=[
            ResolutionWindowRun(
                order=0,
                priority=10,
                task_id="task_weapon_attack",
                description="艾尔德拉用长剑攻击哥布林",
                actor="Aldera",
                target="Goblin",
                narration="长剑命中，地精受伤。",
                field_changes=[
                    {
                        "path": "Goblin.combat.HP",
                        "old_value": "10/10",
                        "new_value": "4/10",
                        "operation": "MOD",
                        "source": "task_weapon_attack",
                    }
                ],
            )
        ],
    )

    store = FakeStore(
        initial_state={"Goblin.combat": "HP: 10/10 | AC: 10"},
        final_state={"Goblin.combat": "HP: 4/10 | AC: 10"},
    )
    workflow = FakeWorkflow(
        store,
        [
            [
                {
                    "_current_task": task,
                    "__interrupt__": {"type": "task_approval"},
                }
            ],
            [
                {
                    "_current_task": task,
                    "_execution_result": execution,
                    "active_window": window,
                    "__interrupt__": {"type": "resolution_window_review"},
                }
            ],
            [
                {
                    "_current_task": None,
                    "active_window": None,
                }
            ],
        ],
    )

    report = run_workflow_cases(
        [case],
        provider="test",
        model="fake",
        workflow_factory=lambda _: (workflow, store),
    )

    assert report.passed_cases == 1
    assert report.results[0].passed is True
    workflow_artifact = report.results[0].artifacts["workflow"]
    assert workflow_artifact["final_state"]["Goblin.combat.HP"] == "4/10"
    assert workflow_artifact["interrupts"][0]["type"] == "task_approval"
    assert "task_sequence_coverage" not in report.results[0].soft_scores
