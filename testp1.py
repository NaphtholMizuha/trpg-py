"""
Phase 1 真实 agent 评测脚本

对同一批 planner / executor / resolver case 连续运行多次，
并输出每次报告与聚合后的稳定性摘要。

使用方式：
  python testp1.py
  python testp1.py --provider deepseek
  python testp1.py --provider openai --output-dir /tmp/trpg-evals
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.rule import Rule
from rich.table import Table

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

from src.evals.cases import load_cases
from src.evals.models import EvalReport
from src.evals.reporting import render_report_summary, write_report
from src.evals.runner import (
    build_real_agents,
    run_executor_cases,
    run_planner_cases,
    run_resolver_cases,
)
from src.utils.logging import configure_logging

configure_logging(debug=True)

app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    rich_markup_mode="rich",
    help="运行 planner/executor/resolver 的 Phase 1 真实评测套件。",
)
console = Console()


def _print_header(title: str) -> None:
    console.print()
    console.print(Rule(f"[bold cyan]{title}[/bold cyan]"))


def _write_suite_summary(
    *,
    report_runs: list[dict[str, EvalReport]],
    provider: str,
    model: str,
    repeats: int,
    output_dir: Path,
) -> Path:
    aggregated_reports: dict[str, dict[str, object]] = {}
    case_stability: dict[str, dict[str, dict[str, float | int]]] = {}

    for run_reports in report_runs:
        for name, report in run_reports.items():
            if name not in aggregated_reports:
                aggregated_reports[name] = {
                    "case_type": report.case_type,
                    "total_cases": 0,
                    "passed_cases": 0,
                    "failed_cases": 0,
                    "pass_rate": 0.0,
                }
                case_stability[name] = {}

            summary = aggregated_reports[name]
            summary["total_cases"] = int(summary["total_cases"]) + report.total_cases
            summary["passed_cases"] = int(summary["passed_cases"]) + report.passed_cases
            summary["failed_cases"] = int(summary["failed_cases"]) + report.failed_cases

            for result in report.results:
                case_summary = case_stability[name].setdefault(
                    result.case_id,
                    {
                        "runs": 0,
                        "passed_runs": 0,
                        "failed_runs": 0,
                        "pass_rate": 0.0,
                    },
                )
                case_summary["runs"] = int(case_summary["runs"]) + 1
                if result.passed:
                    case_summary["passed_runs"] = int(case_summary["passed_runs"]) + 1
                else:
                    case_summary["failed_runs"] = int(case_summary["failed_runs"]) + 1

    for summary in aggregated_reports.values():
        total_cases = int(summary["total_cases"])
        passed_cases = int(summary["passed_cases"])
        summary["pass_rate"] = (passed_cases / total_cases) if total_cases else 0.0

    for agent_cases in case_stability.values():
        for summary in agent_cases.values():
            runs = int(summary["runs"])
            passed_runs = int(summary["passed_runs"])
            summary["pass_rate"] = (passed_runs / runs) if runs else 0.0

    suite_summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "provider": provider,
        "model": model,
        "repeats": repeats,
        "reports": aggregated_reports,
        "case_stability": case_stability,
    }
    summary_path = output_dir / "phase1-summary.json"
    summary_path.write_text(
        json.dumps(suite_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary_path


def _render_suite_table(report_runs: list[dict[str, EvalReport]]) -> None:
    table = Table(title="Phase 1 Eval Summary")
    table.add_column("Agent", style="bold cyan")
    table.add_column("Passed", justify="right")
    table.add_column("Failed", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Pass Rate", justify="right")

    agent_names = ("planner", "executor", "resolver")
    for name in agent_names:
        total_cases = 0
        passed_cases = 0
        failed_cases = 0
        for run_reports in report_runs:
            report = run_reports[name]
            total_cases += report.total_cases
            passed_cases += report.passed_cases
            failed_cases += report.failed_cases
        table.add_row(
            name,
            str(passed_cases),
            str(failed_cases),
            str(total_cases),
            f"{(passed_cases / total_cases) if total_cases else 0.0:.1%}",
        )

    total_cases = sum(report.total_cases for run_reports in report_runs for report in run_reports.values())
    total_passed = sum(report.passed_cases for run_reports in report_runs for report in run_reports.values())
    total_failed = total_cases - total_passed
    total_rate = (total_passed / total_cases) if total_cases else 0.0
    table.add_section()
    table.add_row(
        "ALL",
        str(total_passed),
        str(total_failed),
        str(total_cases),
        f"{total_rate:.1%}",
    )
    console.print(table)


def _write_individual_report(output_dir: Path, filename: str, report: EvalReport) -> Path:
    output_path = output_dir / filename
    write_report(report, output_path)
    return output_path


@app.callback(invoke_without_command=True)
def main(
    provider: str = typer.Option("deepseek", "--provider", help="模型提供商"),
    world_state_path: str = typer.Option(
        "data/world_state.txt",
        "--world-state-path",
        help="world-state 路径",
    ),
    planner_cases_dir: str = typer.Option(
        "evals/planner/cases",
        "--planner-cases-dir",
        help="Planner case 目录",
    ),
    executor_cases_dir: str = typer.Option(
        "evals/executor/cases",
        "--executor-cases-dir",
        help="Executor case 目录",
    ),
    resolver_cases_dir: str = typer.Option(
        "evals/resolver/cases",
        "--resolver-cases-dir",
        help="Resolver case 目录",
    ),
    output_dir: str = typer.Option(
        "evals/reports/phase1",
        "--output-dir",
        help="输出目录",
    ),
    repeats: int = typer.Option(
        5,
        "--repeats",
        min=1,
        help="同一批 case 连续运行次数",
    ),
):
    """运行 Phase 1 真实评测套件。"""
    _print_header("Phase 1 Real Eval")

    console.print(f"Provider: [bold]{provider}[/bold]")
    console.print(f"World state: [bold]{world_state_path}[/bold]")
    console.print(f"Repeats: [bold]{repeats}[/bold]")

    config, planner_agent, executor_agent, resolver_agent = build_real_agents(
        provider,
        world_state_path,
    )

    reports_dir = Path(output_dir) / datetime.now().strftime("%Y%m%d-%H%M%S")
    reports_dir.mkdir(parents=True, exist_ok=True)
    planner_cases = load_cases("planner", planner_cases_dir)
    executor_cases = load_cases("executor", executor_cases_dir)
    resolver_cases = load_cases("resolver", resolver_cases_dir)
    report_runs: list[dict[str, EvalReport]] = []

    for run_index in range(1, repeats + 1):
        run_dir = reports_dir / f"run_{run_index:02d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        _print_header(f"Run {run_index:02d}/{repeats}")

        planner_report = run_planner_cases(
            planner_cases,
            planner_agent,
            provider=provider,
            model=config.llm_model,
        )
        planner_report_path = _write_individual_report(
            run_dir,
            "planner-report.json",
            planner_report,
        )
        console.print(render_report_summary(planner_report))
        console.print(f"Report written to: {planner_report_path}")

        executor_report = run_executor_cases(
            executor_cases,
            executor_agent,
            provider=provider,
            model=config.llm_model,
        )
        executor_report_path = _write_individual_report(
            run_dir,
            "executor-report.json",
            executor_report,
        )
        console.print(render_report_summary(executor_report))
        console.print(f"Report written to: {executor_report_path}")

        resolver_report = run_resolver_cases(
            resolver_cases,
            resolver_agent,
            provider=provider,
            model=config.llm_model,
        )
        resolver_report_path = _write_individual_report(
            run_dir,
            "resolver-report.json",
            resolver_report,
        )
        console.print(render_report_summary(resolver_report))
        console.print(f"Report written to: {resolver_report_path}")

        report_runs.append(
            {
                "planner": planner_report,
                "executor": executor_report,
                "resolver": resolver_report,
            }
        )

    summary_path = _write_suite_summary(
        report_runs=report_runs,
        provider=provider,
        model=config.llm_model,
        repeats=repeats,
        output_dir=reports_dir,
    )

    _print_header("Combined Summary")
    _render_suite_table(report_runs)
    console.print(f"Suite summary written to: {summary_path}")


if __name__ == "__main__":
    app()
