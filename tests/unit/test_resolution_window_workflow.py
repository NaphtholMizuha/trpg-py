from src.types import (
    ExecutionResult,
    Operation,
    ResolutionWindow,
    ResolutionWindowRun,
    StateChange,
    TaskExecution,
    WindowStatus,
)
from src.workflow.nodes import (
    _default_priority,
    _extract_window_shared_context,
    _materialize_resolution,
)


def test_extract_window_shared_context_keeps_structured_lines_only():
    context = (
        "普通描述行\n"
        "[KV Malik.combat] HP: 32/32\n"
        "[RAG 护盾术] 被魔法飞弹指定时可施放\n"
        "[KV Malik.combat] HP: 32/32\n"
    )

    lines = _extract_window_shared_context(context)

    assert lines == [
        "[KV Malik.combat] HP: 32/32",
        "[RAG 护盾术] 被魔法飞弹指定时可施放",
    ]


def test_default_priority_is_higher_than_current_highest_priority():
    window = ResolutionWindow(
        window_id="window_001",
        root_task_id="task_root",
        root_description="demo",
        status=WindowStatus.OPEN,
        shared_context=[],
        runs=[
            ResolutionWindowRun(
                order=0,
                priority=10,
                task_id="task_root",
                description="demo",
            ),
            ResolutionWindowRun(
                order=1,
                priority=9,
                task_id="task_reaction",
                description="reaction",
            ),
        ],
    )

    assert _default_priority(window) == 8


def test_materialize_resolution_overwrites_same_path_with_later_sorted_change():
    window = ResolutionWindow(
        window_id="window_001",
        root_task_id="task_root",
        root_description="demo",
        status=WindowStatus.READY,
        shared_context=[],
        runs=[
            ResolutionWindowRun(
                order=0,
                priority=5,
                task_id="task_a",
                description="first",
                field_changes=[
                    StateChange(
                        path="Aldera.combat.AC",
                        old_value="18",
                        new_value="23",
                        operation=Operation.MOD,
                        source="task_a",
                    )
                ],
            ),
            ResolutionWindowRun(
                order=1,
                priority=10,
                task_id="task_b",
                description="second",
                field_changes=[
                    StateChange(
                        path="Aldera.combat.AC",
                        old_value="23",
                        new_value="18",
                        operation=Operation.MOD,
                        source="task_b",
                    )
                ],
            ),
        ],
    )

    resolution = _materialize_resolution(window)

    assert len(resolution.final_field_changes) == 1
    assert resolution.final_field_changes[0].path == "Aldera.combat.AC"
    assert resolution.final_field_changes[0].new_value == "18"
    assert resolution.final_field_changes[0].source == "resolver:window_001"
    assert len(resolution.discarded_field_changes) == 1
    assert resolution.discarded_field_changes[0].source == "task_a"


def test_resolution_window_run_uses_explicit_priority_for_append_action():
    window = ResolutionWindow(
        window_id="window_001",
        root_task_id="task_root",
        root_description="demo",
        status=WindowStatus.OPEN,
        shared_context=[],
        runs=[],
    )
    task = TaskExecution(
        task_id="task_append",
        description="艾尔德拉施放护盾术",
        context="context",
        actor="Aldera",
        target="Aldera",
        source="dm",
        task_category="normal",
    )
    result = ExecutionResult(
        task_id="task_append",
        success=True,
        narration="护盾术使魔法飞弹伤害无效。",
    )

    run = ResolutionWindowRun.from_task_and_result(task, result, order=len(window.runs), priority=9)

    assert run.priority == 9
    assert run.task_id == "task_append"
