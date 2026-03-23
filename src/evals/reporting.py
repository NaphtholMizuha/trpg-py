"""评测报告输出。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .models import EvalReport


def render_report_summary(report: EvalReport) -> str:
    """渲染终端摘要。"""
    lines = [
        "Eval Summary",
        f"- case_type: {report.case_type}",
        f"- provider: {report.provider or 'N/A'}",
        f"- model: {report.model or 'N/A'}",
        f"- total cases: {report.total_cases}",
        f"- passed: {report.passed_cases}",
        f"- failed: {report.failed_cases}",
        f"- pass_rate: {report.pass_rate:.1%}",
    ]
    return "\n".join(lines)


def build_default_report_path(
    *,
    case_type: str,
    provider: str,
    model: str,
    base_dir: str | Path = "evals/reports",
) -> Path:
    """生成默认报告路径。"""
    safe_provider = (provider or "unknown").replace("/", "_")
    safe_model = (model or "unknown").replace("/", "_")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{timestamp}-{case_type}-{safe_provider}-{safe_model}.json"
    return Path(base_dir) / filename


def write_report(report: EvalReport, path: str | Path) -> Path:
    """把报告写成 JSON 文件。"""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return output_path
