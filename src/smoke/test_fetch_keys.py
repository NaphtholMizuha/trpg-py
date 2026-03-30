from __future__ import annotations

"""
list 工具演示脚本

使用方式:
  python src/smoke/test_fetch_keys.py
  python src/smoke/test_fetch_keys.py --prefix actors.goblin_1
  python src/smoke/test_fetch_keys.py --json
  python src/smoke/test_fetch_keys.py --state-file ./examples/fetch_keys_state.json --prefix actors.hero_1
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

from augury.agent.tools import create_list_tool


DEFAULT_STATE_FILE = PROJECT_ROOT / "examples" / "fetch_keys_state.json"
DEFAULT_NO_MATCH_PREFIX = "actors.goblin_2"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="演示 list 工具的全量与按范围枚举能力")
    parser.add_argument("--prefix", default=None, help="路径前缀过滤，例如 actors.goblin_1")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON 结果")
    parser.add_argument(
        "--state-file",
        default=str(DEFAULT_STATE_FILE),
        help="可选 JSON 文件路径；默认使用 examples/fetch_keys_state.json",
    )
    return parser


def load_state(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("state-file must contain a JSON object")
    return data


def main() -> int:
    args = build_parser().parse_args()
    state_path = Path(args.state_file).expanduser().resolve()
    prefix = args.prefix
    no_match_prefix = DEFAULT_NO_MATCH_PREFIX

    state = load_state(state_path)
    tool = create_list_tool(state=state)

    result_all = tool.invoke({})
    result_prefix = tool.invoke({"prefix": prefix}) if prefix else None
    result_no_match = tool.invoke({"prefix": no_match_prefix})

    if args.json:
        payload = {
            "all": result_all,
            "prefix": result_prefix,
            "no_match": result_no_match,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("=" * 72)
    print("TRPG Agent List Smoke Test")
    print("=" * 72)
    print("全量枚举:")
    print_human_result(result_all)

    if prefix:
        print("-" * 72)
        print(f"按范围枚举: prefix={prefix}")
        print_human_result(result_prefix or {"status": "unknown", "items": []})

    print("-" * 72)
    print(f"无命中演示: prefix={no_match_prefix}")
    print_human_result(result_no_match)
    return 0


def print_human_result(result: dict[str, Any]) -> None:
    status = result.get("status", "unknown")
    print(f"status: {status}")
    if status == "error":
        error = result.get("error", {})
        print(f"error : {error.get('type', 'unknown')} - {error.get('message', '')}")
        return
    items = result.get("items", [])
    if not items:
        print("items : (none)")
    else:
        print(f"items : {len(items)}")
        for item in items:
            print(f"- {item}")
    suggestions = result.get("suggestions", [])
    if suggestions:
        print(f"suggestions: {len(suggestions)}")
        for suggestion in suggestions:
            print(f"* {suggestion}")


if __name__ == "__main__":
    raise SystemExit(main())
