"""评测 runner。"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from time import perf_counter

import typer
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from ..agents import ExecutorAgent, ResolverAgent, create_deep_planner_agent
from ..config import AppConfig
from ..tools.toolkit import TrpgToolkit
from ..utils.kv_patch import KVPatch
from ..workflow import create_workflow
from .cases import load_cases
from .models import (
    EvalCaseResult,
    EvalFailure,
    EvalReport,
    ExecutorEvalCase,
    PlannerEvalCase,
    ResolverEvalCase,
    WorkflowEvalCase,
    WorkflowEvalOutcome,
    WorkflowExecutionTrace,
    WorkflowInterruptTrace,
    WorkflowTaskTrace,
    WorkflowWindowTrace,
)
from .reporting import build_default_report_path, render_report_summary, write_report
from .scorers import (
    score_executor_case,
    score_planner_case,
    score_resolver_case,
    score_workflow_case,
)

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="运行 planner/executor/resolver/workflow 的评测。",
)


def _exception_result(
    *,
    case_id: str,
    case_type: str,
    duration_ms: float,
    code: str,
    message: str,
) -> EvalCaseResult:
    return EvalCaseResult(
        case_id=case_id,
        case_type=case_type,  # type: ignore[arg-type]
        passed=False,
        duration_ms=duration_ms,
        failures=[EvalFailure(code=code, message=message)],
    )


def run_planner_cases(
    cases: list[PlannerEvalCase],
    planner_agent,
    *,
    provider: str = "",
    model: str = "",
) -> EvalReport:
    """运行 planner cases。"""
    results: list[EvalCaseResult] = []
    for case in cases:
        start = perf_counter()
        try:
            task = planner_agent.plan(case.input)
            duration_ms = (perf_counter() - start) * 1000
            results.append(score_planner_case(case, task, duration_ms=duration_ms))
        except Exception as exc:
            duration_ms = (perf_counter() - start) * 1000
            results.append(
                _exception_result(
                    case_id=case.case_id,
                    case_type="planner",
                    duration_ms=duration_ms,
                    code="planner.exception",
                    message=str(exc),
                )
            )
    return EvalReport.from_results(case_type="planner", results=results, provider=provider, model=model)


def run_executor_cases(
    cases: list[ExecutorEvalCase],
    executor_agent,
    *,
    provider: str = "",
    model: str = "",
) -> EvalReport:
    """运行 executor cases。"""
    results: list[EvalCaseResult] = []
    for case in cases:
        start = perf_counter()
        try:
            result = executor_agent.execute(case.task)
            duration_ms = (perf_counter() - start) * 1000
            results.append(score_executor_case(case, result, duration_ms=duration_ms))
        except Exception as exc:
            duration_ms = (perf_counter() - start) * 1000
            results.append(
                _exception_result(
                    case_id=case.case_id,
                    case_type="executor",
                    duration_ms=duration_ms,
                    code="executor.exception",
                    message=str(exc),
                )
            )
    return EvalReport.from_results(case_type="executor", results=results, provider=provider, model=model)


def run_resolver_cases(
    cases: list[ResolverEvalCase],
    resolver_agent,
    *,
    provider: str = "",
    model: str = "",
) -> EvalReport:
    """运行 resolver cases。"""
    results: list[EvalCaseResult] = []
    for case in cases:
        start = perf_counter()
        try:
            result = resolver_agent.resolve(case.window)
            duration_ms = (perf_counter() - start) * 1000
            results.append(score_resolver_case(case, result, duration_ms=duration_ms))
        except Exception as exc:
            duration_ms = (perf_counter() - start) * 1000
            results.append(
                _exception_result(
                    case_id=case.case_id,
                    case_type="resolver",
                    duration_ms=duration_ms,
                    code="resolver.exception",
                    message=str(exc),
                )
    )
    return EvalReport.from_results(case_type="resolver", results=results, provider=provider, model=model)


def run_workflow_cases(
    cases: list[WorkflowEvalCase],
    *,
    provider: str = "",
    model: str = "",
    default_world_state_path: str = "data/world_state.txt",
    workflow_factory=None,
) -> EvalReport:
    """运行 workflow cases。"""
    results: list[EvalCaseResult] = []
    for case in cases:
        start = perf_counter()
        try:
            case_world_state_path = case.world_state_path or default_world_state_path
            if workflow_factory is None:
                workflow, store = build_real_workflow(provider, case_world_state_path)
            else:
                workflow, store = workflow_factory(case_world_state_path)
            outcome = _run_single_workflow_case(case, workflow, store)
            duration_ms = (perf_counter() - start) * 1000
            results.append(score_workflow_case(case, outcome, duration_ms=duration_ms))
        except Exception as exc:
            duration_ms = (perf_counter() - start) * 1000
            results.append(
                _exception_result(
                    case_id=case.case_id,
                    case_type="workflow",
                    duration_ms=duration_ms,
                    code="workflow.exception",
                    message=str(exc),
                )
            )
    return EvalReport.from_results(case_type="workflow", results=results, provider=provider, model=model)


def build_real_agents(provider: str, world_state_path: str):
    config = AppConfig.from_provider(provider)
    if not config.llm_api_key:
        raise typer.BadParameter(f"未配置 {provider} 对应 API key，无法运行真实 agent eval。")

    toolkit = TrpgToolkit(world_state_path=world_state_path, persist=False)
    tools = toolkit.get_tools()
    tool_map = {tool.name: tool for tool in tools}

    planner = create_deep_planner_agent(
        model=config.llm_model,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
        tools=[tool_map["fetch_keys"], tool_map["read"], tool_map["search"]],
        skill_names=None,
    )
    executor = ExecutorAgent(
        model=config.llm_model,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
        tools=[tool_map["evaluate"]],
    )
    resolver = ResolverAgent(
        model=config.llm_model,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
        tools=[tool_map["fetch_keys"], tool_map["read"], tool_map["search"]],
    )
    return config, planner, executor, resolver


def build_real_workflow(provider: str, world_state_path: str):
    config = AppConfig.from_provider(provider)
    if not config.llm_api_key:
        raise typer.BadParameter(f"未配置 {provider} 对应 API key，无法运行真实 workflow eval。")
    workflow_config = replace(
        config,
        world_state_path=world_state_path,
        persist_state=False,
    )
    return create_workflow(config=workflow_config)


def finalize_report(report: EvalReport, output: str | None) -> Path:
    report_path = Path(output) if output else build_default_report_path(
        case_type=report.case_type,
        provider=report.provider,
        model=report.model,
    )
    write_report(report, report_path)
    typer.echo(render_report_summary(report))
    typer.echo(f"Report written to: {report_path}")
    return report_path


@app.command()
def planner(
    cases_dir: str = typer.Option("evals/planner/cases", help="Planner case 目录"),
    provider: str = typer.Option("deepseek", help="模型提供商"),
    world_state_path: str = typer.Option("data/world_state.txt", help="world-state 路径"),
    output: str | None = typer.Option(None, help="JSON 报告输出路径"),
):
    """运行 planner Phase 1 评测。"""
    config, planner_agent, _, _ = build_real_agents(provider, world_state_path)
    cases = load_cases("planner", cases_dir)
    report = run_planner_cases(cases, planner_agent, provider=provider, model=config.llm_model)
    finalize_report(report, output)


@app.command()
def executor(
    cases_dir: str = typer.Option("evals/executor/cases", help="Executor case 目录"),
    provider: str = typer.Option("deepseek", help="模型提供商"),
    world_state_path: str = typer.Option("data/world_state.txt", help="world-state 路径"),
    output: str | None = typer.Option(None, help="JSON 报告输出路径"),
):
    """运行 executor Phase 1 评测。"""
    config, _, executor_agent, _ = build_real_agents(provider, world_state_path)
    cases = load_cases("executor", cases_dir)
    report = run_executor_cases(cases, executor_agent, provider=provider, model=config.llm_model)
    finalize_report(report, output)


@app.command()
def resolver(
    cases_dir: str = typer.Option("evals/resolver/cases", help="Resolver case 目录"),
    provider: str = typer.Option("deepseek", help="模型提供商"),
    world_state_path: str = typer.Option("data/world_state.txt", help="world-state 路径"),
    output: str | None = typer.Option(None, help="JSON 报告输出路径"),
):
    """运行 resolver Phase 1 评测。"""
    config, _, _, resolver_agent = build_real_agents(provider, world_state_path)
    cases = load_cases("resolver", cases_dir)
    report = run_resolver_cases(cases, resolver_agent, provider=provider, model=config.llm_model)
    finalize_report(report, output)


@app.command()
def workflow(
    cases_dir: str = typer.Option("evals/workflow/cases", help="Workflow case 目录"),
    provider: str = typer.Option("deepseek", help="模型提供商"),
    world_state_path: str = typer.Option("data/world_state.txt", help="默认 world-state 路径"),
    output: str | None = typer.Option(None, help="JSON 报告输出路径"),
):
    """运行 workflow 评测。"""
    config = AppConfig.from_provider(provider)
    if not config.llm_api_key:
        raise typer.BadParameter(f"未配置 {provider} 对应 API key，无法运行真实 workflow eval。")
    cases = load_cases("workflow", cases_dir)
    report = run_workflow_cases(
        cases,
        provider=provider,
        model=config.llm_model,
        default_world_state_path=world_state_path,
    )
    finalize_report(report, output)


def _run_single_workflow_case(case: WorkflowEvalCase, workflow, store) -> WorkflowEvalOutcome:
    os.environ.pop("TRPG_AUTO_CONFIRM", None)
    initial_state = _flatten_store_fields(store.to_dict())
    current_input = {"messages": [HumanMessage(content=case.user_input)]}
    config = {"configurable": {"thread_id": f"eval_{case.case_id}"}}

    task_signatures: set[tuple] = set()
    execution_signatures: set[tuple] = set()
    window_state: dict[str, WorkflowWindowTrace] = {}
    interrupts: list[WorkflowInterruptTrace] = []
    script_mismatches: list[str] = []
    script_index = 0
    finished = False
    exception: str | None = None
    outputs_seen = 0
    tasks: list[WorkflowTaskTrace] = []
    executions: list[WorkflowExecutionTrace] = []

    try:
        while outputs_seen < case.max_loops:
            outputs = list(workflow.stream(current_input, config, stream_mode="values"))
            if not outputs:
                finished = True
                break

            for output in outputs:
                outputs_seen += 1
                _collect_workflow_traces(
                    output,
                    task_signatures=task_signatures,
                    execution_signatures=execution_signatures,
                    tasks=tasks,
                    executions=executions,
                    windows=window_state,
                )

            output = outputs[-1]
            interrupt_info = _extract_interrupt_info(output.get("__interrupt__"))
            if interrupt_info is not None:
                interrupt_type = str(interrupt_info.get("type", "unknown"))
                interrupts.append(
                    WorkflowInterruptTrace(type=interrupt_type, payload=interrupt_info)
                )

                resume_payload = _default_interrupt_resume(interrupt_type)
                if script_index < len(case.interrupt_script):
                    expected_step = case.interrupt_script[script_index]
                    if expected_step.type != interrupt_type:
                        script_mismatches.append(
                            f"第 {script_index + 1} 个 interrupt 期望 {expected_step.type}，实际为 {interrupt_type}。"
                        )
                    else:
                        resume_payload = expected_step.resume
                    script_index += 1
                else:
                    script_mismatches.append(f"缺少 {interrupt_type} 的脚本响应。")

                current_input = Command(resume=resume_payload)
                continue

            if output.get("_current_task") is None:
                finished = True
                break

            current_input = None
    except Exception as exc:
        exception = str(exc)

    final_output = outputs[-1] if "outputs" in locals() and outputs else {}
    return WorkflowEvalOutcome(
        finished=finished,
        active_window_present=final_output.get("active_window") is not None,
        initial_state=initial_state,
        final_state=_flatten_store_fields(store.to_dict()),
        tasks=tasks,
        executions=executions,
        windows=list(window_state.values()),
        interrupts=interrupts,
        script_mismatches=script_mismatches,
        unused_script_steps=max(len(case.interrupt_script) - script_index, 0),
        exception=exception,
    )


def _collect_workflow_traces(
    output,
    *,
    task_signatures: set[tuple],
    execution_signatures: set[tuple],
    tasks: list[WorkflowTaskTrace],
    executions: list[WorkflowExecutionTrace],
    windows: dict[str, WorkflowWindowTrace],
) -> None:
    current_task = output.get("_current_task")
    if current_task is not None:
        task_signature = (
            current_task.task_id,
            current_task.description,
            current_task.actor,
            current_task.target,
            tuple(current_task.write_targets),
        )
        if task_signature not in task_signatures:
            task_signatures.add(task_signature)
            tasks.append(
                WorkflowTaskTrace(
                    task_id=current_task.task_id,
                    description=current_task.description,
                    actor=current_task.actor,
                    target=current_task.target,
                    write_targets=list(current_task.write_targets or []),
                )
            )

    execution_result = output.get("_execution_result")
    if execution_result is not None:
        touched_paths = [change.path for change in execution_result.field_changes]
        description = current_task.description if current_task is not None else execution_result.task_id
        execution_signature = (
            execution_result.task_id,
            execution_result.success,
            tuple(touched_paths),
            execution_result.narration,
        )
        if execution_signature not in execution_signatures:
            execution_signatures.add(execution_signature)
            executions.append(
                WorkflowExecutionTrace(
                    task_id=execution_result.task_id,
                    description=description,
                    success=execution_result.success,
                    touched_paths=touched_paths,
                    narration=execution_result.narration,
                )
            )

    active_window = output.get("active_window")
    if active_window is not None:
        existing = windows.get(active_window.window_id)
        run_count = len(active_window.runs)
        if existing is None or run_count > existing.run_count:
            windows[active_window.window_id] = WorkflowWindowTrace(
                window_id=active_window.window_id,
                root_description=active_window.root_description,
                run_count=run_count,
            )


def _extract_interrupt_info(interrupt_data) -> dict | None:
    if not interrupt_data:
        return None
    interrupt_value = interrupt_data
    if isinstance(interrupt_data, (tuple, list)) and interrupt_data:
        interrupt_value = interrupt_data[0]
    if hasattr(interrupt_value, "value"):
        interrupt_value = interrupt_value.value
    if isinstance(interrupt_value, dict):
        return interrupt_value
    return None


def _default_interrupt_resume(interrupt_type: str) -> dict[str, str]:
    if interrupt_type == "task_approval":
        return {"action": "approve"}
    if interrupt_type == "resolution_window_review":
        return {"action": "close_window"}
    return {"action": "continue"}


def _flatten_store_fields(state: dict[str, str]) -> dict[str, str]:
    flattened: dict[str, str] = {}
    for root_key, full_value in state.items():
        patch = KVPatch(full_value or "")
        for field, value in patch.fields.items():
            flattened[f"{root_key}.{field}"] = value
    return flattened


if __name__ == "__main__":
    app()
