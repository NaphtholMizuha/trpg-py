from src.types import ExecutionStep, ExecutionScriptState, PlannedTask
from src.utils.script_parser import (
    build_execution_script_state,
    merge_reworked_steps,
    parse_execution_steps,
    parse_planner_hints,
    parse_task_summary,
    render_runtime_markdown,
)


SCRIPT = """## Task Summary
- Task ID: task_demo
- Description: 马利克施放魔法飞弹
- Actor: 马利克
- Target: 艾尔德拉

## Context
- 魔法飞弹会在命中后直接造成伤害

## Execution Steps
- [step_id: step_1] [status: pending] [phase: declare] [depends_on: none] [source: planner] 宣告施法 :: 马利克宣告施放魔法飞弹。
- [step_id: step_2] [status: pending] [phase: consequence] [depends_on: step_1] [source: planner] 结算伤害 :: 若没有新片段插入，则结算魔法飞弹伤害。

## Planner Hints
- [hint_id: hint_1] [anchor: step_2] [when: before_step] [type: reaction] 艾尔德拉可能在伤害结算前插入护盾术相关片段。

## Query Appendix
无
"""


def test_parse_markdown_script_sections():
    summary = parse_task_summary(SCRIPT)
    assert summary["task_id"] == "task_demo"
    assert summary["actor"] == "马利克"

    steps = parse_execution_steps(SCRIPT)
    assert [step.step_id for step in steps] == ["step_1", "step_2"]
    assert steps[1].depends_on == ["step_1"]

    hints = parse_planner_hints(SCRIPT)
    assert hints[0]["anchor_step_id"] == "step_2"
    assert hints[0]["type"] == "reaction"


def test_merge_reworked_steps_preserves_completed_status():
    task = PlannedTask(
        task_id="task_demo",
        description="demo",
        context=SCRIPT,
        actor="马利克",
        target="艾尔德拉",
    )
    state = build_execution_script_state(task)
    state.steps[0].status = "completed"
    state.active_step_id = "step_2"

    reworked = """## Task Summary
- Task ID: task_demo
- Description: 马利克施放魔法飞弹
- Actor: 马利克
- Target: 艾尔德拉

## Context
- 插入了新的响应步骤

## Execution Steps
- [step_id: step_1] [status: pending] [phase: declare] [depends_on: none] [source: planner] 宣告施法 :: 马利克宣告施放魔法飞弹。
- [step_id: step_1b] [status: pending] [phase: reaction] [depends_on: step_1] [source: rework] 护盾术窗口 :: 艾尔德拉可尝试施放护盾术。
- [step_id: step_2] [status: pending] [phase: consequence] [depends_on: step_1b] [source: planner] 结算伤害 :: 若没有新片段插入，则结算魔法飞弹伤害。

## Planner Hints
- [hint_id: hint_2] [anchor: step_1b] [when: before_step] [type: reaction] 马利克可能在护盾术前插入法术反制片段。

## Query Appendix
无
"""

    merged = merge_reworked_steps(reworked, state)
    step_map = {step.step_id: step for step in merged.steps}
    assert step_map["step_1"].status == "completed"
    assert step_map["step_1b"].status == "pending"
    assert merged.active_step_id == "step_1b"

    rendered = render_runtime_markdown(task, merged)
    assert "[status: completed]" in rendered


def test_merge_reworked_steps_resets_new_completed_steps_to_pending():
    task = PlannedTask(
        task_id="task_demo",
        description="demo",
        context=SCRIPT,
        actor="马利克",
        target="艾尔德拉",
    )
    state = build_execution_script_state(task)
    state.steps[0].status = "completed"

    reworked = """## Task Summary
- Task ID: task_demo
- Description: 马利克施放魔法飞弹
- Actor: 马利克
- Target: 艾尔德拉

## Context
- 插入了新的响应步骤

## Execution Steps
- [step_id: step_1] [status: pending] [phase: declare] [depends_on: none] [source: planner] 宣告施法 :: 马利克宣告施放魔法飞弹。
- [step_id: step_window] [status: completed] [phase: reaction] [depends_on: step_1] [source: rework] 反应确认窗口 :: 确认艾尔德拉是否要施放护盾术。
- [step_id: step_2] [status: pending] [phase: consequence] [depends_on: step_window] [source: planner] 结算伤害 :: 若没有新片段插入，则结算魔法飞弹伤害。

## Planner Hints
- [hint_id: hint_none] [anchor: step_2] [when: none] [type: none] 无

## Query Appendix
无
"""

    merged = merge_reworked_steps(reworked, state)
    step_map = {step.step_id: step for step in merged.steps}
    assert step_map["step_window"].status == "pending"
