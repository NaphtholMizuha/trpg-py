from __future__ import annotations

"""
reads 工具演示脚本

使用方式:
  python src/smoke/test_reads.py
  python src/smoke/test_reads.py --json
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

from augury.planner.tools import create_reads_tool
from smoke.state_loader import load_toml_state


DEFAULT_STATE_FILE = PROJECT_ROOT / "config" / "world_state.toml"
DEFAULT_MATCH_PATHS = [
    "actors.aldera.id",
    "actors.aldera.ac.total",
    "actors.goblin_1.attacks.scimitar.to_hit",
]
DEFAULT_NO_MATCH_PATHS = ["actors.missing_target.id"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="演示 reads 工具的批量状态读取能力")
    parser.add_argument(
        "--state-file",
        default=str(DEFAULT_STATE_FILE),
        help="状态 TOML 文件路径，默认使用 config/world_state.toml",
    )
    parser.add_argument("--json", action="store_true", help="仅输出 JSON 结果")
    return parser


def load_state(path: str | Path) -> dict[str, Any]:
    return load_toml_state(path)


def main() -> int:
    args = build_parser().parse_args()
    state_path = Path(args.state_file).expanduser().resolve()
    state = load_state(state_path)
    tool = create_reads_tool(state=state)
    result_match = tool.invoke({"paths": DEFAULT_MATCH_PATHS})
    result_no_match = tool.invoke({"paths": DEFAULT_NO_MATCH_PATHS})

    if args.json:
        print(
            json.dumps(
                {
                    "match": result_match,
                    "no_match": result_no_match,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print("=" * 72)
    print("TRPG Agent Read Smoke Test")
    print("=" * 72)
    print(f"state_file : {state_path}")
    print(f"match demo : {DEFAULT_MATCH_PATHS}")
    print_human_result(result_match)
    print("-" * 72)
    print(f"no_match demo: {DEFAULT_NO_MATCH_PATHS}")
    print_human_result(result_no_match)
    return 0


def print_human_result(result: dict[str, Any]) -> None:
    status = result.get("status", "unknown")
    print(f"status     : {status}")
    items = result.get("items", [])
    if status == "error":
        error = result.get("error", {})
        print(f"error      : {error.get('type', 'unknown')} - {error.get('message', '')}")
        return
    if items:
        print(f"items      : {len(items)}")
        for item in items:
            if item.get("status") == "ok":
                value = item.get("value")
                rendered = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
                print(f"- {item.get('path')} = {rendered}")
            else:
                print(f"- {item.get('path')} -> no_match")
    suggestions = result.get("suggestions", [])
    if suggestions:
        print("suggestions:")
        for suggestion in suggestions[:5]:
            print(f"- {suggestion}")


if __name__ == "__main__":
    raise SystemExit(main())
