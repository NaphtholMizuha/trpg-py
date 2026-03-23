"""
Workflow 真实评测脚本

对同一批 workflow case 连续运行多次，
并输出每次报告与聚合后的稳定性摘要。

使用方式：
  python test_workflow.py
  python test_workflow.py --provider deepseek
  python test_workflow.py --provider openai --output-dir /tmp/trpg-workflow-evals
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

from src.config import AppConfig
from src.evals.cases import load_cases
from src.evals.models import EvalReport
from src.evals.reporting import render_report_summary, write_report
from src.evals.runner import run_workflow_cases
from src.utils.logging import configure_logging

configure_logging(debug=True)

app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    rich_markup_mode="rich",
    help="运行 workflow 真实评测套件。",
)
console = Console()


def _print_header(title: str) -> None:
    console.print()
    console.print(Rule(f"[bold cyan]{title}[/bold cyan]"))


def _write_suite_summary(
    *,
    reports: list[EvalReport],
    provider: str,
    model: str,
    repeats: int,
    output_dir: Path,
) -> Path:
    total_cases = sum(report.total_cases for report in reports)
    passed_cases = sum(report.passed_cases for report in reports)
    failed_cases = total_cases - passed_cases
    pass_rate = (passed_cases / total_cases) if total_cases else 0.0

    case_stability: dict[str, dict[str, float | int]] = {}
    signal_breakdown = {
        "no_task": {"count": 0, "rate": 0.0},
        "no_execution": {"count": 0, "rate": 0.0},
        "execution_issue": {"count": 0, "rate": 0.0},
        "state_mismatch": {"count": 0, "rate": 0.0},
    }
    for report in reports:
        for result in report.results:
            summary = case_stability.setdefault(
                result.case_id,
                {
                    "runs": 0,
                    "passed_runs": 0,
                    "failed_runs": 0,
                    "pass_rate": 0.0,
                },
            )
            summary["runs"] = int(summary["runs"]) + 1
            if result.passed:
                summary["passed_runs"] = int(summary["passed_runs"]) + 1
            else:
                summary["failed_runs"] = int(summary["failed_runs"]) + 1
                for signal in _collect_failure_signals(result):
                    signal_breakdown[signal]["count"] = int(signal_breakdown[signal]["count"]) + 1

    for summary in case_stability.values():
        runs = int(summary["runs"])
        passed_runs = int(summary["passed_runs"])
        summary["pass_rate"] = (passed_runs / runs) if runs else 0.0

    for signal_summary in signal_breakdown.values():
        signal_summary["rate"] = (
            int(signal_summary["count"]) / failed_cases if failed_cases else 0.0
        )

    suite_summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "provider": provider,
        "model": model,
        "repeats": repeats,
        "report": {
            "case_type": "workflow",
            "total_cases": total_cases,
            "passed_cases": passed_cases,
            "failed_cases": failed_cases,
            "pass_rate": pass_rate,
        },
        "signal_breakdown": signal_breakdown,
        "case_stability": case_stability,
    }
    summary_path = output_dir / "workflow-summary.json"
    summary_path.write_text(
        json.dumps(suite_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary_path


def _render_suite_table(reports: list[EvalReport]) -> None:
    table = Table(title="Workflow Eval Summary")
    table.add_column("Run", style="bold cyan")
    table.add_column("Passed", justify="right")
    table.add_column("Failed", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Pass Rate", justify="right")
    table.add_column("No Task", justify="right")
    table.add_column("No Exec", justify="right")
    table.add_column("Exec Issue", justify="right")
    table.add_column("State Wrong", justify="right")

    total_cases = 0
    total_passed = 0
    total_no_task = 0
    total_no_execution = 0
    total_execution_issue = 0
    total_state_mismatch = 0
    for index, report in enumerate(reports, start=1):
        total_cases += report.total_cases
        total_passed += report.passed_cases
        breakdown = _signal_breakdown_for_report(report)
        total_no_task += breakdown["no_task"]
        total_no_execution += breakdown["no_execution"]
        total_execution_issue += breakdown["execution_issue"]
        total_state_mismatch += breakdown["state_mismatch"]
        table.add_row(
            f"run_{index:02d}",
            str(report.passed_cases),
            str(report.failed_cases),
            str(report.total_cases),
            f"{report.pass_rate:.1%}",
            _format_ratio(breakdown["no_task"], report.failed_cases),
            _format_ratio(breakdown["no_execution"], report.failed_cases),
            _format_ratio(breakdown["execution_issue"], report.failed_cases),
            _format_ratio(breakdown["state_mismatch"], report.failed_cases),
        )

    total_failed = total_cases - total_passed
    total_rate = (total_passed / total_cases) if total_cases else 0.0
    table.add_section()
    table.add_row(
        "ALL",
        str(total_passed),
        str(total_failed),
        str(total_cases),
        f"{total_rate:.1%}",
        _format_ratio(total_no_task, total_failed),
        _format_ratio(total_no_execution, total_failed),
        _format_ratio(total_execution_issue, total_failed),
        _format_ratio(total_state_mismatch, total_failed),
    )
    console.print(table)


def _write_individual_report(output_dir: Path, filename: str, report: EvalReport) -> Path:
    output_path = output_dir / filename
    write_report(report, output_path)
    return output_path


def _signal_breakdown_for_report(report: EvalReport) -> dict[str, int]:
    breakdown = {
        "no_task": 0,
        "no_execution": 0,
        "execution_issue": 0,
        "state_mismatch": 0,
    }
    for result in report.results:
        if result.passed:
            continue
        for signal in _collect_failure_signals(result):
            breakdown[signal] += 1
    return breakdown


def _collect_failure_signals(result) -> set[str]:
    workflow = result.artifacts.get("workflow", {})
    tasks = workflow.get("tasks", [])
    executions = workflow.get("executions", [])
    failure_codes = {failure.get("code") for failure in result.failures}
    signals: set[str] = set()

    if not tasks:
        signals.add("no_task")

    if tasks and not executions:
        signals.add("no_execution")

    if any(
        (not item.get("success"))
        or (not item.get("touched_paths"))
        or (item.get("narration") == "executor_stalled")
        for item in executions
    ):
        signals.add("execution_issue")

    if (
        "workflow.field_behavior_mismatch" in failure_codes
        or "workflow.final_state_mismatch" in failure_codes
    ):
        signals.add("state_mismatch")

    return signals


def _format_ratio(count: int, denominator: int) -> str:
    if denominator <= 0:
        return "0/0"
    return f"{count}/{denominator} ({count / denominator:.0%})"


@app.callback(invoke_without_command=True)
def main(
    provider: str = typer.Option("deepseek", "--provider", help="模型提供商"),
    world_state_path: str = typer.Option(
        "data/world_state.txt",
        "--world-state-path",
        help="默认 world-state 路径",
    ),
    workflow_cases_dir: str = typer.Option(
        "evals/workflow/cases",
        "--workflow-cases-dir",
        help="Workflow case 目录",
    ),
    output_dir: str = typer.Option(
        "evals/reports/workflow",
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
    """运行 workflow 真实评测套件。"""
    _print_header("Workflow Real Eval")

    console.print(f"Provider: [bold]{provider}[/bold]")
    console.print(f"Default world state: [bold]{world_state_path}[/bold]")
    console.print(f"Repeats: [bold]{repeats}[/bold]")

    config = AppConfig.from_provider(provider)
    if not config.llm_api_key:
        raise typer.BadParameter(f"未配置 {provider} 对应 API key，无法运行真实 workflow eval。")

    reports_dir = Path(output_dir) / datetime.now().strftime("%Y%m%d-%H%M%S")
    reports_dir.mkdir(parents=True, exist_ok=True)
    workflow_cases = load_cases("workflow", workflow_cases_dir)
    reports: list[EvalReport] = []

    for run_index in range(1, repeats + 1):
        run_dir = reports_dir / f"run_{run_index:02d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        _print_header(f"Run {run_index:02d}/{repeats}")

        workflow_report = run_workflow_cases(
            workflow_cases,
            provider=provider,
            model=config.llm_model,
            default_world_state_path=world_state_path,
        )
        workflow_report_path = _write_individual_report(
            run_dir,
            "workflow-report.json",
            workflow_report,
        )
        console.print(render_report_summary(workflow_report))
        console.print(f"Report written to: {workflow_report_path}")
        reports.append(workflow_report)

    _print_header("Aggregated Summary")
    _render_suite_table(reports)
    summary_path = _write_suite_summary(
        reports=reports,
        provider=provider,
        model=config.llm_model,
        repeats=repeats,
        output_dir=reports_dir,
    )
    console.print(f"Suite summary written to: {summary_path}")


if __name__ == "__main__":
    app()
