from __future__ import annotations

"""
read 工具演示脚本

使用方式:
  python src/smoke/test_reads.py
  python src/smoke/test_reads.py --json
  python src/smoke/test_reads.py --path actors.aldera.id --path actors.aldera.ac
  python src/smoke/test_reads.py --state-file ./config/world_state.toml
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

from smoke.state_loader import load_toml_state
from augury.planner.tools import create_read_tool


DEFAULT_STATE_FILE = PROJECT_ROOT / "config" / "world_state.toml"
DEFAULT_PATHS = ["actors.aldera.id", "actors.aldera.ac", "actors.goblin_1.attacks.scimitar.to_hit"]
DEFAULT_NO_MATCH_PATHS = ["actors.missing_target.id"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="演示 read 工具的状态值读取能力")
    parser.add_argument(
        "--state-file",
        default=str(DEFAULT_STATE_FILE),
        help="状态 TOML 文件路径，默认使用 config/world_state.toml",
    )
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        default=None,
        help="要读取的点路径；可重复传入。未提供时使用默认演示路径。",
    )
    parser.add_argument("--json", action="store_true", help="仅输出 JSON 结果")
    return parser


def load_state(path: str | Path) -> dict[str, Any]:
    return load_toml_state(path)


def main() -> int:
    args = build_parser().parse_args()
    state_path = Path(args.state_file).expanduser().resolve()
    paths = list(args.paths or DEFAULT_PATHS)

    state = load_state(state_path)
    tool = create_read_tool(state=state)
    result_match = tool.invoke({"paths": paths})
    result_no_match = tool.invoke({"paths": DEFAULT_NO_MATCH_PATHS})

    if args.json:
        payload = {
            "match": result_match,
            "no_match": result_no_match,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("=" * 72)
    print("TRPG Agent Read Smoke Test")
    print("=" * 72)
    print(f"state_file : {state_path}")
    print("match demo :")
    print_human_result(result_match)
    print("-" * 72)
    print("no_match demo:")
    print_human_result(result_no_match)
    return 0


def print_human_result(result: dict[str, Any]) -> None:
    status = result.get("status", "unknown")
    print(f"status     : {status}")
    if status == "error":
        error = result.get("error", {})
        print(f"error      : {error.get('type', 'unknown')} - {error.get('message', '')}")
        return
    items = result.get("items", [])
    if not items:
        print("items      : (none)")
    else:
        print(f"items      : {len(items)}")
        for item in items:
            path = item.get("path", "")
            item_status = item.get("status", "unknown")
            if item_status == "ok":
                print(f"- {path} = {json.dumps(item.get('value'), ensure_ascii=False)}")
                continue
            error = item.get("error", {})
            print(f"- {path} -> {item_status}: {error.get('message', '')}")
            suggestions = item.get("suggestions", [])
            for suggestion in suggestions:
                print(f"  suggestion: {suggestion}")
    suggestions = result.get("suggestions", [])
    if suggestions:
        print(f"suggestions: {len(suggestions)}")
        for suggestion in suggestions:
            print(f"* {suggestion}")


if __name__ == "__main__":
    raise SystemExit(main())
