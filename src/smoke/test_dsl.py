from __future__ import annotations

"""
dsl_node 烟雾测试脚本

使用方式:
  python src/smoke/test_dsl.py
  python src/smoke/test_dsl.py --json
  python src/smoke/test_dsl.py --draft-file ./output/test_task_draft.json
  python src/smoke/test_dsl.py --draft-dir ./examples/taskdrafts --log-dir ./logs/dsl
  python src/smoke/test_dsl.py --config ./config/config.toml
"""

import argparse
import json
import sys
import traceback
from copy import deepcopy
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from augury import execute_task
from augury.config import (
    DEFAULT_PROJECT_CONFIG_PATH,
    load_project_config,
    resolve_path_from_config,
)
from augury.planner.nodes import DslNode, DslNodeDependencies
from augury.planner.task_document import TaskDraft
from augury.planner.tools import create_lint_tool, create_template_tool
from smoke.execution_helpers import build_smoke_roller, render_change_lines, summarize_state_changes
from smoke.state_loader import load_toml_state


DEFAULT_DRAFT_FILE = PROJECT_ROOT / "output" / "test_task_draft.json"
DEFAULT_STATE_FILE = PROJECT_ROOT / "config" / "world_state.toml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="演示 dsl_node 将 TaskDraft 翻译为 TaskDocument 的能力")
    parser.add_argument(
        "--draft-file",
        default=str(DEFAULT_DRAFT_FILE),
        help="TaskDraft JSON 文件路径，默认使用 output/test_task_draft.json",
    )
    parser.add_argument(
        "--draft-dir",
        default=None,
        help="批量模式：TaskDraft JSON 目录，目录下每个 *.json 会被逐个解析并写日志",
    )
    parser.add_argument(
        "--log-dir",
        default=str(PROJECT_ROOT / "logs" / "dsl"),
        help="批量模式日志输出目录，默认 logs/dsl",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_PROJECT_CONFIG_PATH),
        help="项目配置 TOML 路径，默认使用 config/config.toml",
    )
    parser.add_argument(
        "--state-file",
        default=None,
        help="状态 TOML 文件路径，默认从 config.toml 的 planner.smoke.world_state_file 解析",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="仅输出包含 draft、DSL、lint、执行结果与状态变化的 JSON 结果",
    )
    return parser


def load_task_draft(path: str | Path) -> TaskDraft:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return TaskDraft.model_validate(payload)


def build_dsl_node(*, config_path: str | Path) -> DslNode:
    template_tool = create_template_tool() if create_template_tool is not None else None
    lint_tool = create_lint_tool() if create_lint_tool is not None else None
    return DslNode(
        DslNodeDependencies(
            template_tool=template_tool,
            lint_tool=lint_tool,
            config_path=config_path,
        )
    )


def resolve_state_file(*, config_path: str | Path, override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    try:
        config = load_project_config(config_path=config_path, resolve_secrets=False)
    except Exception:
        return DEFAULT_STATE_FILE.resolve()
    return resolve_path_from_config(
        config.planner.smoke.world_state_file,
        config_path=config_path,
    )


def load_state(path: str | Path) -> dict[str, Any]:
    return load_toml_state(path)


def execute_generated_task(
    task_document: dict[str, Any],
    *,
    state: dict[str, Any],
) -> dict[str, Any]:
    report = execute_task(task_document, state, roller=build_smoke_roller())
    return report.to_dict()


def main() -> int:
    args = build_parser().parse_args()
    config_path = Path(args.config).expanduser().resolve()
    state_path = resolve_state_file(config_path=config_path, override=args.state_file)
    node = build_dsl_node(config_path=config_path)
    if args.draft_dir:
        draft_dir = Path(args.draft_dir).expanduser().resolve()
        log_dir = Path(args.log_dir).expanduser().resolve()
        return run_batch_mode(
            draft_dir=draft_dir,
            log_dir=log_dir,
            node=node,
            state_path=state_path,
            config_path=config_path,
            as_json=args.json,
        )

    draft_path = Path(args.draft_file).expanduser().resolve()
    payload = run_single_draft(
        draft_path=draft_path,
        node=node,
        state_path=state_path,
    )
    return render_single_result(payload=payload, config_path=config_path, draft_path=draft_path, as_json=args.json)


def run_single_draft(
    *,
    draft_path: Path,
    node: DslNode,
    state_path: Path,
) -> dict[str, Any]:
    draft = load_task_draft(draft_path)
    task_document, lint_result = node.run(draft)
    execution_result = build_execution_result(
        task_document=task_document,
        lint_result=lint_result,
        state_path=state_path,
    )
    return {
        "draft": draft.model_dump(),
        "task_document": task_document,
        "lint_result": lint_result,
        "execution_result": execution_result,
        "state_changes": execution_result.get("state_changes", []),
        "state_file": str(state_path),
    }


def render_single_result(
    *,
    payload: dict[str, Any],
    config_path: Path,
    draft_path: Path,
    as_json: bool,
) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    draft = TaskDraft.model_validate(payload["draft"])
    task_document = payload["task_document"]
    lint_result = payload["lint_result"]
    execution_result = payload["execution_result"]

    print("=" * 72)
    print("TRPG Planner DslNode Smoke Test")
    print("=" * 72)
    print(f"config_file : {config_path}")
    print(f"draft_file  : {draft_path}")
    print(f"state_file  : {payload['state_file']}")
    print(f"instruction : {draft.instruction}")
    print(f"task_id     : {task_document.get('task_id', '(missing)')}")
    print(f"lint_status : {format_lint_status(lint_result)}")
    lint_calls = extract_lint_calls(lint_result)
    if lint_calls is not None:
        print(f"lint_calls  : {lint_calls}")
    fallback_used = extract_used_fallback(lint_result)
    if fallback_used is not None:
        print(f"used_fallback: {'yes' if fallback_used else 'no'}")
    print(f"execution_status : {format_execution_status(execution_result)}")
    print("task_document:")
    print(indent_block(json.dumps(task_document, ensure_ascii=False, indent=2)))
    print("lint_result:")
    print(indent_block(json.dumps(lint_result, ensure_ascii=False, indent=2)))
    print("execution_result:")
    print(indent_block(json.dumps(execution_result, ensure_ascii=False, indent=2)))
    print("state_changes:")
    for line in render_change_lines(execution_result.get("state_changes", [])):
        print(line)
    return 0


def run_batch_mode(
    *,
    draft_dir: Path,
    log_dir: Path,
    node: DslNode,
    state_path: Path,
    config_path: Path,
    as_json: bool,
) -> int:
    if not draft_dir.exists() or not draft_dir.is_dir():
        raise FileNotFoundError(f"draft directory not found: {draft_dir}")
    draft_files = sorted(path for path in draft_dir.glob("*.json") if path.is_file())
    if not draft_files:
        raise ValueError(f"no task draft files found in: {draft_dir}")

    log_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    for draft_path in draft_files:
        try:
            payload = run_single_draft(
                draft_path=draft_path,
                node=node,
                state_path=state_path,
            )
        except Exception as exc:
            payload = {
                "draft_file": str(draft_path),
                "error": {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                },
                "state_file": str(state_path),
            }
        log_path = log_dir / f"{draft_path.stem}.log"
        log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lint_status = "error"
        execution_status = "error"
        if "error" not in payload:
            lint_status = format_lint_status(payload.get("lint_result"))
            execution_status = format_execution_status(payload.get("execution_result"))
        summaries.append(
            {
                "draft_file": str(draft_path),
                "log_file": str(log_path),
                "lint_status": lint_status,
                "execution_status": execution_status,
            }
        )

    if as_json:
        print(
            json.dumps(
                {
                    "config_file": str(config_path),
                    "state_file": str(state_path),
                    "draft_dir": str(draft_dir),
                    "log_dir": str(log_dir),
                    "count": len(summaries),
                    "results": summaries,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print("=" * 72)
    print("TRPG Planner DslNode Batch Smoke Test")
    print("=" * 72)
    print(f"config_file : {config_path}")
    print(f"state_file  : {state_path}")
    print(f"draft_dir   : {draft_dir}")
    print(f"log_dir     : {log_dir}")
    print(f"files       : {len(summaries)}")
    print("-" * 72)
    for item in summaries:
        print(f"- {Path(item['draft_file']).name}")
        print(f"  lint      : {item['lint_status']}")
        print(f"  execution : {item['execution_status']}")
        print(f"  log       : {item['log_file']}")
    return 0


def build_execution_result(
    *,
    task_document: dict[str, Any],
    lint_result: dict[str, Any] | None,
    state_path: str | Path,
) -> dict[str, Any]:
    if lint_result is None or lint_result.get("status") != "valid":
        return {
            "status": "skipped",
            "reason": "lint_invalid",
            "report": None,
            "state_changes": [],
        }

    state = load_state(state_path)
    initial_state = deepcopy(state)
    report = execute_generated_task(task_document, state=state)
    changes = summarize_state_changes(initial_state, state)
    return {
        "status": report.get("status", "unknown"),
        "reason": None,
        "report": report,
        "state_changes": changes,
    }


def format_lint_status(lint_result: dict[str, Any] | None) -> str:
    if lint_result is None:
        return "(not_run)"
    return str(lint_result.get("status", "unknown"))


def format_execution_status(execution_result: dict[str, Any] | None) -> str:
    if execution_result is None:
        return "(not_run)"
    status = execution_result.get("status", "unknown")
    reason = execution_result.get("reason")
    if reason:
        return f"{status} ({reason})"
    return str(status)


def extract_lint_calls(lint_result: dict[str, Any] | None) -> int | None:
    if lint_result is None:
        return None
    meta = lint_result.get("dsl_node_meta")
    if not isinstance(meta, dict):
        return None
    value = meta.get("lint_calls")
    return value if isinstance(value, int) else None


def extract_used_fallback(lint_result: dict[str, Any] | None) -> bool | None:
    if lint_result is None:
        return None
    meta = lint_result.get("dsl_node_meta")
    if not isinstance(meta, dict):
        return None
    value = meta.get("used_fallback")
    return value if isinstance(value, bool) else None


def indent_block(text: str) -> str:
    return "\n".join(f"  {line}" for line in text.splitlines() or [""])


if __name__ == "__main__":
    raise SystemExit(main())
