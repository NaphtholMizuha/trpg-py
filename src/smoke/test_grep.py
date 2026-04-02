from __future__ import annotations

"""
grep 工具演示脚本

使用方式:
  python src/smoke/test_grep.py
  python src/smoke/test_grep.py --json
  python src/smoke/test_grep.py --expression "goblin && scimitar && to_hit"
  python src/smoke/test_grep.py --expression "(aldera && ac) || (malik && slot)"
  python src/smoke/test_grep.py --state-file ./config/world_state.toml
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
from augury.planner.tools import create_grep_tool


DEFAULT_STATE_FILE = PROJECT_ROOT / "config" / "world_state.toml"
DEFAULT_EXPRESSIONS = ["goblin && scimitar && to_hit", "(aldera && ac) || (malik && slot)"]
DEFAULT_NO_MATCH_EXPRESSIONS = ["xyzzy && plugh"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="演示 grep 工具的布尔表达式状态行匹配能力")
    parser.add_argument(
        "--state-file",
        default=str(DEFAULT_STATE_FILE),
        help="状态 TOML 文件路径，默认使用 config/world_state.toml",
    )
    parser.add_argument(
        "--expression",
        action="append",
        dest="expressions",
        default=None,
        help="布尔表达式；可重复传入。未提供时使用默认演示表达式。",
    )
    parser.add_argument("--json", action="store_true", help="仅输出 JSON 结果")
    return parser


def load_state(path: str | Path) -> dict[str, Any]:
    return load_toml_state(path)


def main() -> int:
    args = build_parser().parse_args()
    state_path = Path(args.state_file).expanduser().resolve()
    expressions = list(args.expressions or DEFAULT_EXPRESSIONS)

    state = load_state(state_path)
    tool = create_grep_tool(state=state)
    result_match = tool.invoke({"expressions": expressions})
    result_no_match = tool.invoke({"expressions": DEFAULT_NO_MATCH_EXPRESSIONS})

    if args.json:
        payload = {
            "match": result_match,
            "no_match": result_no_match,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("=" * 72)
    print("TRPG Agent Grep Smoke Test")
    print("=" * 72)
    print(f"state_file : {state_path}")
    print(f"match demo : {expressions}")
    print_human_result(result_match)
    print("-" * 72)
    print(f"no_match demo: {DEFAULT_NO_MATCH_EXPRESSIONS}")
    print_human_result(result_no_match)
    return 0


def print_human_result(result: dict[str, Any]) -> None:
    status = result.get("status", "unknown")
    print(f"status     : {status}")
    if status == "error":
        error = result.get("error", {})
        print(f"error      : {error.get('type', 'unknown')} - {error.get('message', '')}")
        return
    matches = result.get("matches", [])
    if not matches:
        print("matches    : (none)")
        return
    print(f"matches    : {len(matches)}")
    for item in matches[:5]:
        print(
            "- "
            + f"{item.get('key')} = {json.dumps(item.get('value'), ensure_ascii=False) if not isinstance(item.get('value'), str) else item.get('value')}"
            + f" (sim={item.get('sim')})"
        )


if __name__ == "__main__":
    raise SystemExit(main())
