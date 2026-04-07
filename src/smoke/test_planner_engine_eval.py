from __future__ import annotations

"""
planner -> engine 端到端评测脚本

使用方式:
  python src/smoke/test_planner_engine_eval.py
  python src/smoke/test_planner_engine_eval.py --json
  python src/smoke/test_planner_engine_eval.py --case 01_aldera_longsword_goblin_1
  python src/smoke/test_planner_engine_eval.py --cases-file ./examples/evals/planner_e2e/cases.json
  python src/smoke/test_planner_engine_eval.py --state-file ./examples/evals/planner_e2e/world_state.toml
  python src/smoke/test_planner_engine_eval.py --log-dir ./logs/planner_e2e
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
from smoke.planner_e2e_eval import (
    EvalSuite,
    load_eval_state,
    load_eval_suite,
    run_eval_case,
    summarize_eval_results,
    write_eval_logs,
)


DEFAULT_CASES_FILE = PROJECT_ROOT / "examples" / "evals" / "planner_e2e" / "cases.json"
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs" / "planner_e2e"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="批量运行 planner -> engine 端到端评测")
    parser.add_argument(
        "--cases-file",
        default=str(DEFAULT_CASES_FILE),
        help="评测案例 manifest 文件路径，默认使用 examples/evals/planner_e2e/cases.json",
    )
    parser.add_argument(
        "--state-file",
        default=None,
        help="覆盖 suite 自带的 world state 文件路径",
    )
    parser.add_argument(
        "--log-dir",
        default=str(DEFAULT_LOG_DIR),
        help="日志输出目录，默认 logs/planner_e2e",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_PROJECT_CONFIG_PATH),
        help="项目配置 TOML 路径，默认使用 config/config.toml",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="只运行指定 case_id，可重复传入多个 --case",
    )
    parser.add_argument("--json", action="store_true", help="输出结构化 JSON 结果")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    cases_path = Path(args.cases_file).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()
    suite = load_eval_suite(cases_path)
    state_path = Path(args.state_file).expanduser().resolve() if args.state_file else suite.world_state_file
    filtered_suite = filter_suite_cases(suite, requested_case_ids=list(args.case))
    filtered_suite = EvalSuite(
        suite_name=filtered_suite.suite_name,
        world_state_file=state_path,
        default_dice=list(filtered_suite.default_dice),
        cases=list(filtered_suite.cases),
    )
    initial_state = load_eval_state(state_path)

    results = [
        run_eval_case(case, suite=filtered_suite, initial_state=initial_state, config_path=config_path)
        for case in filtered_suite.cases
    ]
    summary = summarize_eval_results(results)
    written = write_eval_logs(results, log_dir=args.log_dir, summary=summary)
    payload = {
        "suite_name": filtered_suite.suite_name,
        "config_file": str(config_path),
        "cases_file": str(cases_path),
        "state_file": str(state_path),
        "log_dir": written["log_dir"],
        "summary_file": written["summary_file"],
        "count": len(results),
        "results": written["results"],
        "summary": written["summary"],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("=" * 72)
    print("TRPG Planner Engine End-to-End Eval")
    print("=" * 72)
    print(f"config_file : {config_path}")
    print(f"cases_file  : {cases_path}")
    print(f"state_file  : {state_path}")
    print(f"log_dir     : {written['log_dir']}")
    print(f"summary_file: {written['summary_file']}")
    print(f"cases       : {len(results)}")
    print(f"passed      : {summary['passed']}")
    print(f"failed      : {summary['failed']}")
    print("-" * 72)
    for item in written["summary"]["results"]:
        print(f"- {item['case_id']}: {'PASS' if item['passed'] else 'FAIL'}")
        print(f"  workflow  : {item['workflow_status']}")
        print(f"  execution : {item['execution_status']}")
        if item["failure_reasons"]:
            print(f"  failures  : {'; '.join(item['failure_reasons'])}")
        print(f"  log       : {item['log_file']}")
    return 0


def filter_suite_cases(suite: EvalSuite, *, requested_case_ids: list[str]) -> EvalSuite:
    if not requested_case_ids:
        return suite
    requested = set(requested_case_ids)
    filtered = [case for case in suite.cases if case.case_id in requested]
    if len(filtered) != len(requested):
        found = {case.case_id for case in filtered}
        missing = sorted(requested - found)
        raise ValueError(f"unknown case ids: {', '.join(missing)}")
    return EvalSuite(
        suite_name=suite.suite_name,
        world_state_file=suite.world_state_file,
        default_dice=list(suite.default_dice),
        cases=filtered,
    )


if __name__ == "__main__":
    raise SystemExit(main())
