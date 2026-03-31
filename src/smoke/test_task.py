from __future__ import annotations

"""
task_node 烟雾测试脚本

使用方式:
  python src/smoke/test_task.py
  python src/smoke/test_task.py --json
  python src/smoke/test_task.py --instruction "Malik attacks Aldera with a longsword."
  python src/smoke/test_task.py --state-file ./config/world_state.toml
  python src/smoke/test_task.py --config ./config/config.toml
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from augury.config import DEFAULT_PROJECT_CONFIG_PATH
from augury.planner.nodes import TaskNode, TaskNodeDependencies
from augury.planner.task_document import TaskDraft
from augury.planner.tools import create_grep_tool
from smoke.state_loader import load_toml_state


DEFAULT_STATE_FILE = PROJECT_ROOT / "config" / "world_state.toml"
DEFAULT_INSTRUCTION = "Review Aldera AC before the next turn."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="演示 task_node 将指令翻译为 TaskDraft 的能力")
    parser.add_argument(
        "--instruction",
        default=DEFAULT_INSTRUCTION,
        help="要交给 task_node 的 DM 指令，默认使用内置演示指令。",
    )
    parser.add_argument(
        "--state-file",
        default=str(DEFAULT_STATE_FILE),
        help="状态 TOML 文件路径，默认使用 config/world_state.toml",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_PROJECT_CONFIG_PATH),
        help="项目配置 TOML 路径，默认使用 config/config.toml",
    )
    parser.add_argument("--json", action="store_true", help="仅输出 TaskDraft JSON")
    return parser


def load_state(path: str | Path) -> dict[str, Any]:
    return load_toml_state(path)


def build_task_node(*, state: dict[str, Any], config_path: str | Path) -> TaskNode:
    return TaskNode(
        TaskNodeDependencies(
            grep_tool=create_grep_tool(state=state),
            config_path=config_path,
        )
    )


def main() -> int:
    args = build_parser().parse_args()
    state_path = Path(args.state_file).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()
    state = load_state(state_path)
    node = build_task_node(state=state, config_path=config_path)
    draft = node.run(args.instruction)

    if args.json:
        print(json.dumps(draft.model_dump(), ensure_ascii=False, indent=2))
        return 0

    print("=" * 72)
    print("TRPG Planner TaskNode Smoke Test")
    print("=" * 72)
    print(f"config_file : {config_path}")
    print(f"state_file  : {state_path}")
    print(f"instruction : {args.instruction}")
    print_human_result(draft)
    return 0


def print_human_result(draft: TaskDraft) -> None:
    print(f"task        : {draft.task}")
    print_list("reads", draft.reads)
    print_list("judgments", draft.judgments)
    print_list("writes", draft.writes)
    print_list("missing_info", draft.missing_info)
    print_list("assumptions", draft.assumptions)
    if draft.context_lines:
        print_list("context_lines", draft.context_lines)


def print_list(label: str, values: list[Any]) -> None:
    if not values:
        print(f"{label:<12}: (none)")
        return
    print(f"{label:<12}: {len(values)}")
    for value in values:
        rendered = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        print(f"- {rendered}")


if __name__ == "__main__":
    raise SystemExit(main())
