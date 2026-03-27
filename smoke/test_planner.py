from __future__ import annotations

"""
planner 功能演示脚本

使用方式:
  python smoke/test_planner.py
  python smoke/test_planner.py --json
  python smoke/test_planner.py --debug
  python smoke/test_planner.py --instruction "张三用长剑攻击地精"
  python smoke/test_planner.py --config config/config.toml
  python smoke/test_planner.py --thread-id <thread> --resume-json '{"decisions":[{"type":"approve"}]}'
"""

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from smoke.state_loader import load_toml_state
from trpg_py.agent import PlannerRequest, create_planner
from trpg_py.config import DEFAULT_PROJECT_CONFIG_PATH, load_project_config, resolve_path_from_config


DEFAULT_INSTRUCTION = "哥布林用弯刀攻击 aldera"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="使用真实 planner、真实 search 和真实 fetch_keys 链路做一次烟雾测试"
    )
    parser.add_argument("--instruction", default=DEFAULT_INSTRUCTION, help="DM 指令文本")
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
    parser.add_argument("--debug", action="store_true", help="输出 planner 调试轨迹摘要或结构化 debug 负载")
    parser.add_argument("--json", action="store_true", help="只打印结构化结果")
    return parser


def load_demo_state(config_path: str) -> dict[str, Any]:
    project_config = load_project_config(config_path, resolve_secrets=False)
    world_state_path = resolve_path_from_config(
        project_config.planner.smoke.world_state_file,
        config_path=config_path,
    )
    try:
        return load_toml_state(world_state_path)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Planner smoke world state file was not found: {world_state_path}") from exc
    except OSError as exc:
        raise RuntimeError(f"Failed to read planner smoke world state file {world_state_path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise RuntimeError(f"Planner smoke world state file is not valid TOML: {world_state_path}: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"Planner smoke world state file must contain a TOML table root: {world_state_path}: {exc}") from exc


def run_planner(
    *,
    planner: Any,
    instruction: str,
    thread_id: str | None = None,
    resume: Any = None,
    debug: bool = False,
) -> dict[str, Any]:
    result = planner.plan(
        PlannerRequest(
            instruction=instruction,
            thread_id=thread_id,
            resume=resume,
            debug=debug,
        )
    )
    payload = result.model_dump(exclude_none=True)
    log_path = getattr(planner, "last_run_log_path", None)
    if log_path:
        payload["planner_log_path"] = str(log_path)
    return payload


def main() -> int:
    args = build_parser().parse_args()
    config_path = str(Path(args.config).expanduser())
    planner: Any | None = None
    while True:
        try:
            state = load_demo_state(config_path)
            planner = create_planner(config_path=config_path, state=state)
        except Exception as exc:
            payload = {
                "status": "blocked",
                "error": {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                },
            }
            log_path = getattr(planner, "last_run_log_path", None) if planner is not None else None
            if log_path:
                payload["planner_log_path"] = str(log_path)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return 0
            print_human_result(
                args.instruction,
                payload,
                config_path=config_path,
                thread_id=args.thread_id,
                resumed=args.resume_json is not None,
                debug=args.debug,
            )
            return 0
        break

    resume = parse_resume_json(args.resume_json)
    thread_id = args.thread_id

    while True:
        try:
            payload = run_planner(
                planner=planner,
                instruction=args.instruction,
                thread_id=thread_id,
                resume=resume,
                debug=args.debug,
            )
        except Exception as exc:
            payload = {
                "status": "blocked",
                "error": {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                },
            }

        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        print_human_result(
            args.instruction,
            payload,
            config_path=config_path,
            thread_id=thread_id,
            resumed=resume is not None,
            debug=args.debug,
        )
        next_thread_id = _extract_resume_thread_id(payload)
        if next_thread_id is None:
            return 0
        next_resume = prompt_for_resume_payload(payload)
        if next_resume is None:
            return 0
        thread_id = next_thread_id
        resume = next_resume


def parse_resume_json(raw_value: str | None) -> Any:
    if raw_value is None:
        return None
    return json.loads(raw_value)


def _extract_resume_thread_id(result: dict[str, Any]) -> str | None:
    resume = result.get("resume", {})
    if not isinstance(resume, dict):
        return None
    thread_id = resume.get("thread_id")
    return str(thread_id) if thread_id else None


def prompt_for_resume_payload(result: dict[str, Any]) -> Any | None:
    print("hitl       : waiting for user input")
    for question in result.get("questions", []):
        if not isinstance(question, dict):
            continue
        options = question.get("options", [])
        if isinstance(options, list) and options:
            print(f"options    : {', '.join(str(option) for option in options)}")
    print("input      : approve | reject | quit | <raw json>")
    while True:
        raw_value = input("decision   : ").strip()
        if raw_value in {"quit", "exit"}:
            print("hitl       : stopped by user")
            return None
        if raw_value == "approve":
            return {"decisions": [{"type": "approve"}]}
        if raw_value == "reject":
            return {"decisions": [{"type": "reject"}]}
        try:
            return json.loads(raw_value)
        except json.JSONDecodeError:
            print("invalid    : expected approve/reject/quit or a JSON object")


def print_human_result(
    instruction: str,
    result: dict[str, Any],
    *,
    config_path: str,
    thread_id: str | None,
    resumed: bool,
    debug: bool,
) -> int:
    print("=" * 72)
    print("TRPG Agent Planner Smoke Test")
    print("=" * 72)
    print(f"instruction: {instruction}")
    print(f"config     : {config_path}")
    print("tools      : search=real, fetch_keys=real, reads=real, lint=real")
    if thread_id:
        print(f"thread_id  : {thread_id}")
    if resumed:
        print("mode       : resume")
    if debug:
        print("debug      : on")
    print(f"status     : {result.get('status', 'unknown')}")

    assumptions = result.get("assumptions", [])
    if assumptions:
        print("assumptions:")
        for assumption in assumptions:
            print(f"- {assumption}")

    missing_info = result.get("missing_info", [])
    if missing_info:
        print(f"missing    : {', '.join(missing_info)}")

    if result.get("status") == "ready":
        task_document = result.get("task_document", {})
        print(f"task_id    : {task_document.get('task_id', '(missing)')}")
        print(f"steps      : {len(task_document.get('steps', []))}")
        print_log_path_summary(result)
        print_debug_summary(result)
        return 0

    if result.get("status") == "needs_human":
        print("questions:")
        for question in result.get("questions", []):
            print(f"- {question.get('question', '')}")
        resume = result.get("resume", {})
        if isinstance(resume, dict) and resume.get("thread_id"):
            print(f"resume     : {resume['thread_id']}")
        print_failure_summary(result)
        print_log_path_summary(result)
        print_debug_summary(result)
        return 0

    error = result.get("error", {})
    print(f"error      : {error.get('type', 'unknown')} - {error.get('message', '')}")
    print_failure_summary(result)
    print_log_path_summary(result)
    print_debug_summary(result)
    return 0


def print_failure_summary(result: dict[str, Any]) -> None:
    reason = result.get("reason")
    if reason:
        print(f"reason     : {reason}")

    error = result.get("error", {})
    printed_detail = False
    if reason == "task_document_validation" and isinstance(error, dict):
        error_type = error.get("type")
        if error_type:
            print(f"error_type : {error_type}")
        error_message = error.get("message")
        if error_message:
            print(f"detail     : {error_message}")
            printed_detail = True

    debug = result.get("debug", {})
    if isinstance(debug, dict):
        message = debug.get("failure_message")
        stage = debug.get("failure_stage")
        if stage:
            print(f"failure    : {stage}")
        if message and not printed_detail:
            print(f"detail     : {message}")


def print_debug_summary(result: dict[str, Any]) -> None:
    debug = result.get("debug")
    if not isinstance(debug, dict):
        return

    attempts = debug.get("attempts", [])
    print(f"debug_try  : {len(attempts)}")
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        round_id = attempt.get("round", "?")
        input_mode = attempt.get("input_mode", "unknown")
        print(f"- round {round_id} ({input_mode})")
        validation_error = attempt.get("validation_error")
        if validation_error:
            print(f"  validation: {validation_error}")
        repair_feedback = attempt.get("repair_feedback")
        if repair_feedback:
            print("  repaired : yes")


def print_log_path_summary(result: dict[str, Any]) -> None:
    log_path = result.get("planner_log_path")
    if log_path:
        print(f"log_path   : {log_path}")


if __name__ == "__main__":
    raise SystemExit(main())
