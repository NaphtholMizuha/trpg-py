from __future__ import annotations

"""
dsl_node 烟雾测试脚本

使用方式:
  python src/smoke/test_dsl.py
  python src/smoke/test_dsl.py --json
  python src/smoke/test_dsl.py --draft-file ./output/test_task_draft.json
  python src/smoke/test_dsl.py --config ./config/config.toml
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
from augury.planner.nodes import DslNode, DslNodeDependencies
from augury.planner.task_document import TaskDraft
from augury.planner.tools import create_lint_tool


DEFAULT_DRAFT_FILE = PROJECT_ROOT / "output" / "test_task_draft.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="演示 dsl_node 将 TaskDraft 翻译为 TaskDocument 的能力")
    parser.add_argument(
        "--draft-file",
        default=str(DEFAULT_DRAFT_FILE),
        help="TaskDraft JSON 文件路径，默认使用 output/test_task_draft.json",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_PROJECT_CONFIG_PATH),
        help="项目配置 TOML 路径，默认使用 config/config.toml",
    )
    parser.add_argument("--json", action="store_true", help="仅输出包含 draft、DSL 和 lint 的 JSON 结果")
    return parser


def load_task_draft(path: str | Path) -> TaskDraft:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return TaskDraft.model_validate(payload)


def build_dsl_node(*, config_path: str | Path) -> DslNode:
    lint_tool = create_lint_tool() if create_lint_tool is not None else None
    return DslNode(
        DslNodeDependencies(
            lint_tool=lint_tool,
            config_path=config_path,
        )
    )


def main() -> int:
    args = build_parser().parse_args()
    draft_path = Path(args.draft_file).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()
    draft = load_task_draft(draft_path)
    node = build_dsl_node(config_path=config_path)
    task_document, lint_result = node.run(draft)

    payload = {
        "draft": draft.model_dump(),
        "task_document": task_document,
        "lint_result": lint_result,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("=" * 72)
    print("TRPG Planner DslNode Smoke Test")
    print("=" * 72)
    print(f"config_file : {config_path}")
    print(f"draft_file  : {draft_path}")
    print(f"instruction : {draft.instruction}")
    print(f"task_id     : {task_document.get('task_id', '(missing)')}")
    print(f"lint_status : {format_lint_status(lint_result)}")
    print("task_document:")
    print(indent_block(json.dumps(task_document, ensure_ascii=False, indent=2)))
    print("lint_result:")
    print(indent_block(json.dumps(lint_result, ensure_ascii=False, indent=2)))
    return 0


def format_lint_status(lint_result: dict[str, Any] | None) -> str:
    if lint_result is None:
        return "(not_run)"
    return str(lint_result.get("status", "unknown"))


def indent_block(text: str) -> str:
    return "\n".join(f"  {line}" for line in text.splitlines() or [""])


if __name__ == "__main__":
    raise SystemExit(main())
