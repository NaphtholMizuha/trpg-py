from __future__ import annotations

"""
planner + engine 端到端烟雾测试脚本

使用方式:
  python src/smoke/test_planner_engine.py
  python src/smoke/test_planner_engine.py --json
  python src/smoke/test_planner_engine.py --instruction "哥布林用弯刀攻击 aldera"
  python src/smoke/test_planner_engine.py --roll 12 --roll 4
  python src/smoke/test_planner_engine.py --thread-id <thread> --resume-json '{"decisions":[{"type":"approve"}]}'
"""

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
except ImportError:  # pragma: no cover - optional presentation dependency
    Console = None
    Panel = None
    Rule = None
    Table = None

from smoke.test_engine import format_value, render_summary
from smoke.test_planner import (
    DEFAULT_INSTRUCTION as DEFAULT_PLANNER_INSTRUCTION,
    _extract_resume_thread_id,
    build_stage_summary,
    load_demo_state,
    parse_resume_json,
    prompt_for_resume_payload,
    run_planner,
)
from augury import FixedDiceRoller, execute_task
from augury.agent import create_planner
from augury.config import DEFAULT_PROJECT_CONFIG_PATH


DEFAULT_ROLLS = [20, 4, 4, 4, 4]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="使用真实 planner 与 engine 链路做一次从 instruction 到状态变化的烟雾测试"
    )
    parser.add_argument("--instruction", default=DEFAULT_PLANNER_INSTRUCTION, help="DM 指令文本")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_PROJECT_CONFIG_PATH),
        help="planner/search 统一配置路径，默认使用 config/config.toml",
    )
    parser.add_argument("--thread-id", default=None, help="可选恢复规划使用的 thread_id")
    parser.add_argument(
        "--resume-json",
        default=None,
        help="可选 JSON 字符串；提供后将以 resume 模式继续一次被 HITL 中断的规划",
    )
    parser.add_argument(
        "--roll",
        type=int,
        action="append",
        default=None,
        help="追加一个固定骰子值；未提供时默认使用可复现的 [20, 4, 4, 4, 4]",
    )
    parser.add_argument("--json", action="store_true", help="只打印结构化结果")
    return parser


def execute_planned_task(
    task_document: dict[str, Any],
    *,
    state: dict[str, Any],
    rolls: list[int],
) -> dict[str, Any]:
    initial_state = deepcopy(state)
    try:
        report = execute_task(task_document, state, roller=FixedDiceRoller(rolls))
    except Exception as exc:
        return {
            "status": "error",
            "rolls": rolls,
            "initial_state": initial_state,
            "final_state": state,
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
            },
        }
    return {
        "status": "ok",
        "rolls": rolls,
        "initial_state": initial_state,
        "final_state": state,
        "report": report.to_dict(),
    }


def build_output_payload(
    *,
    instruction: str,
    config_path: str,
    rolls: list[int],
    planner_result: dict[str, Any],
    execution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "instruction": instruction,
        "config": config_path,
        "rolls": rolls,
        "planner": planner_result,
    }
    if execution is not None:
        payload["execution"] = execution
    return payload


def main() -> int:
    args = build_parser().parse_args()
    config_path = str(Path(args.config).expanduser())
    rolls = list(args.roll or DEFAULT_ROLLS)

    try:
        state = load_demo_state(config_path)
        planner = create_planner(config_path=config_path, state=state)
    except Exception as exc:
        planner_result = {
            "status": "blocked",
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
            },
        }
        payload = build_output_payload(
            instruction=args.instruction,
            config_path=config_path,
            rolls=rolls,
            planner_result=planner_result,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        print_human_result(
            instruction=args.instruction,
            config_path=config_path,
            rolls=rolls,
            planner_result=planner_result,
            thread_id=args.thread_id,
            resumed=args.resume_json is not None,
        )
        return 0

    resume = parse_resume_json(args.resume_json)
    thread_id = args.thread_id

    while True:
        try:
            planner_result = run_planner(
                planner=planner,
                instruction=args.instruction,
                thread_id=thread_id,
                resume=resume,
                debug=True,
            )
        except Exception as exc:
            planner_result = {
                "status": "blocked",
                "error": {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                },
            }
            log_path = getattr(planner, "last_run_log_path", None)
            if log_path:
                planner_result["planner_log_path"] = str(log_path)

        if planner_result.get("status") == "ready":
            task_document = planner_result.get("task_document", {})
            execution = execute_planned_task(task_document, state=state, rolls=rolls)
            payload = build_output_payload(
                instruction=args.instruction,
                config_path=config_path,
                rolls=rolls,
                planner_result=planner_result,
                execution=execution,
            )
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return 0
            print_human_result(
                instruction=args.instruction,
                config_path=config_path,
                rolls=rolls,
                planner_result=planner_result,
                execution=execution,
                thread_id=thread_id,
                resumed=resume is not None,
            )
            return 0

        payload = build_output_payload(
            instruction=args.instruction,
            config_path=config_path,
            rolls=rolls,
            planner_result=planner_result,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        print_human_result(
            instruction=args.instruction,
            config_path=config_path,
            rolls=rolls,
            planner_result=planner_result,
            thread_id=thread_id,
            resumed=resume is not None,
        )

        if planner_result.get("status") == "blocked":
            return 0

        next_thread_id = _extract_resume_thread_id(planner_result)
        if next_thread_id is None:
            return 0
        next_resume = prompt_for_resume_payload(planner_result)
        if next_resume is None:
            return 0
        thread_id = next_thread_id
        resume = next_resume


def print_human_result(
    *,
    instruction: str,
    config_path: str,
    rolls: list[int],
    planner_result: dict[str, Any],
    execution: dict[str, Any] | None = None,
    thread_id: str | None = None,
    resumed: bool = False,
) -> None:
    if Console is None or Panel is None or Rule is None or Table is None:
        print_plain_result(
            instruction=instruction,
            config_path=config_path,
            rolls=rolls,
            planner_result=planner_result,
            execution=execution,
            thread_id=thread_id,
            resumed=resumed,
        )
        return

    console = Console(file=sys.stdout, force_terminal=False, color_system=None, width=100, soft_wrap=True)
    console.print(Panel.fit(_build_overview_table(instruction, config_path, rolls, thread_id, resumed), title="TRPG Planner + Engine Smoke Test"))
    console.print(Rule("Planner Stage"))
    console.print(Panel.fit(_build_planner_table(planner_result), title="Planner Result"))

    status = planner_result.get("status")
    if status == "needs_human":
        questions = planner_result.get("questions", [])
        if questions:
            console.print(Panel.fit(_build_questions_table(questions, planner_result.get("resume")), title="Questions"))
        reason_panel = _build_failure_panel(planner_result)
        if reason_panel is not None:
            console.print(reason_panel)
        return

    if status == "blocked":
        reason_panel = _build_failure_panel(planner_result)
        if reason_panel is not None:
            console.print(reason_panel)
        return

    if execution is None:
        return

    console.print(Rule("Execution Stage"))
    console.print(Panel.fit(_build_execution_table(execution), title="Execution Result"))
    console.print(Panel.fit(_build_execution_summary_text(planner_result, execution), title="Execution Summary"))
    changes_table = _build_changes_table(execution)
    if changes_table is not None:
        console.print(Panel.fit(changes_table, title="Applied Changes"))


def print_plain_result(
    *,
    instruction: str,
    config_path: str,
    rolls: list[int],
    planner_result: dict[str, Any],
    execution: dict[str, Any] | None,
    thread_id: str | None,
    resumed: bool,
) -> None:
    print("=" * 72)
    print("TRPG Planner + Engine Smoke Test")
    print("=" * 72)
    print(f"instruction: {instruction}")
    print(f"config     : {config_path}")
    print(f"rolls      : {', '.join(str(value) for value in rolls)}")
    if thread_id:
        print(f"thread_id  : {thread_id}")
    if resumed:
        print("mode       : resume")
    print("Planner Stage")
    print(f"status     : {planner_result.get('status', 'unknown')}")
    stage_summary = build_stage_summary(planner_result)
    if stage_summary:
        print(f"stages     : {stage_summary}")
    if planner_result.get("status") == "ready":
        task_document = planner_result.get("task_document", {})
        print(f"task_id    : {task_document.get('task_id', '(missing)')}")
        print(f"steps      : {len(task_document.get('steps', []))}")
    elif planner_result.get("status") == "needs_human":
        reason = planner_result.get("reason")
        if reason:
            print(f"reason     : {reason}")
        missing_info = planner_result.get("missing_info", [])
        if missing_info:
            print(f"missing    : {', '.join(str(item) for item in missing_info)}")
        print("questions:")
        for question in planner_result.get("questions", []):
            print(f"- {question.get('question', '')}")
        error = planner_result.get("error", {})
        if isinstance(error, dict) and error:
            print(f"error      : {error.get('type', 'unknown')} - {error.get('message', '')}")
        log_path = planner_result.get("planner_log_path")
        if log_path:
            print(f"log_path   : {log_path}")
    else:
        reason = planner_result.get("reason")
        if reason:
            print(f"reason     : {reason}")
        error = planner_result.get("error", {})
        print(f"error      : {error.get('type', 'unknown')} - {error.get('message', '')}")
        log_path = planner_result.get("planner_log_path")
        if log_path:
            print(f"log_path   : {log_path}")
    if execution is None:
        return
    print("Execution Stage")
    print(f"status     : {execution.get('status', 'unknown')}")
    report = execution.get("report", {})
    if isinstance(report, dict):
        print(f"engine     : {report.get('status', 'unknown')}")
        print(f"changes    : {len(report.get('applied_changes', []))}")
        print(_build_execution_summary_text(planner_result, execution))


def _build_overview_table(
    instruction: str,
    config_path: str,
    rolls: list[int],
    thread_id: str | None,
    resumed: bool,
) -> Any:
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("instruction", instruction)
    table.add_row("config", config_path)
    table.add_row("rolls", ", ".join(str(value) for value in rolls))
    if thread_id:
        table.add_row("thread_id", thread_id)
    if resumed:
        table.add_row("mode", "resume")
    return table


def _build_planner_table(planner_result: dict[str, Any]) -> Any:
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("status", str(planner_result.get("status", "unknown")))

    assumptions = planner_result.get("assumptions", [])
    if assumptions:
        table.add_row("assumptions", "\n".join(f"- {item}" for item in assumptions))

    missing_info = planner_result.get("missing_info", [])
    if missing_info:
        table.add_row("missing", ", ".join(str(item) for item in missing_info))
    stage_summary = build_stage_summary(planner_result)
    if stage_summary:
        table.add_row("stages", stage_summary)

    reason = planner_result.get("reason")
    if reason:
        table.add_row("reason", str(reason))

    if planner_result.get("status") == "ready":
        task_document = planner_result.get("task_document", {})
        table.add_row("task_id", str(task_document.get("task_id", "(missing)")))
        table.add_row("steps", str(len(task_document.get("steps", []))))
        log_path = planner_result.get("planner_log_path")
        if log_path:
            table.add_row("log_path", str(log_path))
        return table

    error = planner_result.get("error", {})
    if isinstance(error, dict) and error:
        table.add_row("error", f"{error.get('type', 'unknown')} - {error.get('message', '')}")
    log_path = planner_result.get("planner_log_path")
    if log_path:
        table.add_row("log_path", str(log_path))
    return table


def _build_questions_table(questions: list[dict[str, Any]], resume: Any) -> Any:
    table = Table(show_header=True, header_style="bold")
    table.add_column("Question")
    table.add_column("Options", overflow="fold")
    for question in questions:
        if not isinstance(question, dict):
            continue
        options = question.get("options", [])
        option_text = ", ".join(str(item) for item in options) if isinstance(options, list) and options else "-"
        table.add_row(str(question.get("question", "")), option_text)
    if isinstance(resume, dict) and resume.get("thread_id"):
        table.add_row("resume thread", str(resume["thread_id"]))
    return table


def _build_failure_panel(planner_result: dict[str, Any]) -> Any | None:
    if Panel is None or Table is None:
        return None
    reason = planner_result.get("reason")
    error = planner_result.get("error", {})
    if not reason and not error:
        return None
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold")
    table.add_column()
    if reason:
        table.add_row("reason", str(reason))
    if isinstance(error, dict) and error:
        table.add_row("error_type", str(error.get("type", "unknown")))
        table.add_row("detail", str(error.get("message", "")))
    log_path = planner_result.get("planner_log_path")
    if log_path:
        table.add_row("log_path", str(log_path))
    return Panel.fit(table, title="Failure Detail")


def _build_execution_table(execution: dict[str, Any]) -> Any:
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("stage_status", str(execution.get("status", "unknown")))
    table.add_row("rolls", ", ".join(str(value) for value in execution.get("rolls", [])))

    error = execution.get("error", {})
    if isinstance(error, dict) and error:
        table.add_row("error", f"{error.get('type', 'unknown')} - {error.get('message', '')}")
        return table

    report = execution.get("report", {})
    if isinstance(report, dict):
        table.add_row("engine_status", str(report.get("status", "unknown")))
        table.add_row("steps", str(len(report.get("step_reports", []))))
        table.add_row("changes", str(len(report.get("applied_changes", []))))
    return table


def _build_execution_summary_text(planner_result: dict[str, Any], execution: dict[str, Any]) -> str:
    error = execution.get("error", {})
    if isinstance(error, dict) and error:
        return f"Execution error: {error.get('type', 'unknown')} - {error.get('message', '')}"
    report = execution.get("report", {})
    if not isinstance(report, dict):
        return "Execution report is unavailable."
    task_document = planner_result.get("task_document", {})
    task_name = str(task_document.get("task_id", report.get("task_id", "planned-task")))
    return render_summary(task_name, {"report": report})


def _build_changes_table(execution: dict[str, Any]) -> Any | None:
    if Table is None:
        return None
    report = execution.get("report", {})
    if not isinstance(report, dict):
        return None
    changes = report.get("applied_changes", [])
    table = Table(show_header=True, header_style="bold")
    table.add_column("Path")
    table.add_column("Old")
    table.add_column("New")
    if not changes:
        table.add_row("(none)", "-", "-")
        return table
    for change in changes:
        table.add_row(
            str(change.get("path", "")),
            format_value(change.get("old_value")),
            format_value(change.get("new_value")),
        )
    return table


if __name__ == "__main__":
    raise SystemExit(main())
