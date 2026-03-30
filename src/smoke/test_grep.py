from __future__ import annotations

"""
grep 工具演示脚本

使用方式:
  python src/smoke/test_grep.py
  python src/smoke/test_grep.py --json
  python src/smoke/test_grep.py --query "goblin scimitar to_hit"
  python src/smoke/test_grep.py --term goblin --term scimitar --term to_hit
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
from augury.agent.tools import create_grep_tool


DEFAULT_STATE_FILE = PROJECT_ROOT / "config" / "world_state.toml"
DEFAULT_QUERY = "goblin scimitar to_hit"
DEFAULT_TERMS = ["aldera", "ac"]
DEFAULT_NO_MATCH_TERMS = ["xyzzy", "plugh", "nonexistent_leaf"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="演示 grep 工具的叶子路径检索能力")
    parser.add_argument(
        "--state-file",
        default=str(DEFAULT_STATE_FILE),
        help="状态 TOML 文件路径，默认使用 config/world_state.toml",
    )
    parser.add_argument("--query", default=DEFAULT_QUERY, help="可选自由文本查询")
    parser.add_argument(
        "--term",
        action="append",
        dest="terms",
        default=None,
        help="可选关键词；可重复传入。未提供时使用默认演示关键词。",
    )
    parser.add_argument("--json", action="store_true", help="仅输出 JSON 结果")
    return parser


def load_state(path: str | Path) -> dict[str, Any]:
    return load_toml_state(path)


def main() -> int:
    args = build_parser().parse_args()
    state_path = Path(args.state_file).expanduser().resolve()
    terms = list(args.terms or DEFAULT_TERMS)

    state = load_state(state_path)
    tool = create_grep_tool(state=state)
    result_query = tool.invoke({"query": args.query})
    result_terms = tool.invoke({"terms": terms})
    result_no_match = tool.invoke({"terms": DEFAULT_NO_MATCH_TERMS})

    if args.json:
        payload = {
            "query": result_query,
            "terms": result_terms,
            "no_match": result_no_match,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("=" * 72)
    print("TRPG Agent Grep Smoke Test")
    print("=" * 72)
    print(f"state_file : {state_path}")
    print(f"query demo : {args.query}")
    print_human_result(result_query)
    print("-" * 72)
    print(f"terms demo : {terms}")
    print_human_result(result_terms)
    print("-" * 72)
    print(f"no_match demo: {DEFAULT_NO_MATCH_TERMS}")
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
    for item in matches:
        print(f"- {item.get('path', '')} (score={item.get('score', 0)})")
        if item.get("matched_terms"):
            print(f"  terms     : {', '.join(str(term) for term in item['matched_terms'])}")
        if item.get("reason"):
            print(f"  reason    : {item['reason']}")


if __name__ == "__main__":
    raise SystemExit(main())
