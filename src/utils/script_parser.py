"""
Markdown 执行稿解析与渲染辅助。
"""
from __future__ import annotations

import re

from ..types import (
    ExecutionStep,
    ExecutionScriptState,
    PlannedTask,
    STEP_PHASES,
)


SECTION_HEADERS = (
    "Task Summary",
    "Context",
    "Execution Steps",
    "Planner Hints",
    "Query Appendix",
)


def normalize_step_phase(phase: str) -> str:
    raw = (phase or "").strip().lower()
    mapping = {
        "main": "declare",
        "reaction": "action",
        "consequence": "resolution",
        "reaction_window": "choice",
        "damage": "resolution",
    }
    normalized = mapping.get(raw, raw)
    return normalized if normalized in STEP_PHASES else "action"


def extract_section(markdown: str, title: str) -> str:
    pattern = rf"^## {re.escape(title)}\s*$"
    match = re.search(pattern, markdown, flags=re.MULTILINE)
    if not match:
        return ""
    start = match.end()

    next_header = None
    for header in SECTION_HEADERS:
        if header == title:
            continue
        candidate = re.search(
            rf"^## {re.escape(header)}\s*$",
            markdown[start:],
            flags=re.MULTILINE,
        )
        if candidate:
            offset = start + candidate.start()
            if next_header is None or offset < next_header:
                next_header = offset

    return markdown[start:next_header].strip() if next_header is not None else markdown[start:].strip()


def parse_task_summary(markdown: str) -> dict[str, str]:
    section = extract_section(markdown, "Task Summary")
    summary: dict[str, str] = {}
    for line in section.splitlines():
        cleaned = line.strip()
        if not cleaned.startswith("-"):
            continue
        body = cleaned[1:].strip()
        if ":" not in body:
            continue
        key, value = body.split(":", 1)
        summary[key.strip().lower().replace(" ", "_")] = value.strip()
    return summary


def parse_execution_steps(markdown: str) -> list[ExecutionStep]:
    section = extract_section(markdown, "Execution Steps")
    steps: list[ExecutionStep] = []
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line.startswith("- [step_id:"):
            continue

        def _capture(name: str, default: str = "") -> str:
            match = re.search(rf"\[{name}:\s*([^\]]+)\]", line)
            return match.group(1).strip() if match else default

        step_id = _capture("step_id")
        status = _capture("status", "pending")
        phase = normalize_step_phase(_capture("phase", "declare"))
        depends = _capture("depends_on", "")
        source = _capture("source", "planner")
        after = line.rsplit("]", 1)[-1].strip()
        title, instruction = (after.split("::", 1) + [""])[:2]
        depends_on = [item.strip() for item in depends.split(",") if item.strip() and item.strip().lower() != "none"]
        steps.append(
            ExecutionStep(
                step_id=step_id,
                title=title.strip() or step_id,
                instruction=instruction.strip() or title.strip(),
                status=status,
                phase=phase,
                depends_on=depends_on,
                source=source,
            )
        )
    return steps


def parse_planner_hints(markdown: str) -> list[dict[str, str]]:
    section = extract_section(markdown, "Planner Hints")
    hints: list[dict[str, str]] = []
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line.startswith("- [hint_id:"):
            continue

        def _capture(name: str, default: str = "") -> str:
            match = re.search(rf"\[{name}:\s*([^\]]+)\]", line)
            return match.group(1).strip() if match else default

        hints.append(
            {
                "hint_id": _capture("hint_id"),
                "anchor_step_id": _capture("anchor"),
                "when": _capture("when"),
                "type": _capture("type"),
                "description": line.rsplit("]", 1)[-1].strip(),
            }
        )
    return hints


def render_planner_hints(hints: list[dict[str, str]]) -> str:
    if not hints:
        return "- [hint_id: hint_none] [anchor: none] [when: none] [type: none] 无"
    lines: list[str] = []
    for hint in hints:
        lines.append(
            f"- [hint_id: {hint.get('hint_id', 'hint_unknown')}] "
            f"[anchor: {hint.get('anchor_step_id', 'none')}] "
            f"[when: {hint.get('when', 'none')}] "
            f"[type: {hint.get('type', 'none')}] "
            f"{hint.get('description', '').strip()}"
        )
    return "\n".join(lines)


def build_execution_script_state(task: PlannedTask) -> ExecutionScriptState:
    steps = parse_execution_steps(task.context)
    active = next((step.step_id for step in steps if step.status != "completed"), None)
    return ExecutionScriptState(
        task_id=task.task_id,
        steps=steps,
        active_step_id=active,
        script_markdown=task.context,
        history=[],
    )


def merge_reworked_steps(
    reworked_markdown: str,
    previous_state: ExecutionScriptState,
) -> ExecutionScriptState:
    previous_by_id = {step.step_id: step for step in previous_state.steps}
    new_steps = parse_execution_steps(reworked_markdown)
    for step in new_steps:
        old = previous_by_id.get(step.step_id)
        if old is not None:
            step.status = old.status
        else:
            # Do not trust planner rework to mark newly inserted steps as already done.
            step.status = "pending"
    active = next((step.step_id for step in new_steps if step.status != "completed"), None)
    return ExecutionScriptState(
        task_id=previous_state.task_id,
        steps=new_steps,
        active_step_id=active,
        script_markdown=reworked_markdown,
        history=list(previous_state.history),
    )


def render_runtime_markdown(
    task: PlannedTask,
    script_state: ExecutionScriptState | None,
) -> str:
    if script_state is None:
        return task.context

    steps_by_id = {step.step_id: step for step in script_state.steps}
    lines: list[str] = []
    inside_steps = False
    for raw_line in task.context.splitlines():
        stripped = raw_line.strip()
        if stripped == "## Execution Steps":
            inside_steps = True
            lines.append(raw_line)
            for step in script_state.steps:
                depends = ", ".join(step.depends_on) if step.depends_on else "none"
                lines.append(
                    f"- [step_id: {step.step_id}] [status: {step.status}] [phase: {step.phase}] "
                    f"[depends_on: {depends}] [source: {step.source}] {step.title} :: {step.instruction}"
                )
            continue

        if inside_steps and stripped.startswith("- [step_id:"):
            continue

        if inside_steps and stripped.startswith("## ") and stripped != "## Execution Steps":
            inside_steps = False

        lines.append(raw_line)

    if "## Execution Steps" not in task.context:
        lines.append("## Execution Steps")
        for step in script_state.steps:
            depends = ", ".join(step.depends_on) if step.depends_on else "none"
            lines.append(
                f"- [step_id: {step.step_id}] [status: {step.status}] [phase: {step.phase}] "
                f"[depends_on: {depends}] [source: {step.source}] {step.title} :: {step.instruction}"
            )

    return "\n".join(lines).strip()


def render_full_markdown(
    task: PlannedTask,
    script_state: ExecutionScriptState,
    hints: list[dict[str, str]] | None = None,
) -> str:
    task_summary = extract_section(task.context, "Task Summary")
    context = extract_section(task.context, "Context")
    query_appendix = extract_section(task.context, "Query Appendix")
    hint_section = render_planner_hints(hints if hints is not None else parse_planner_hints(task.context))

    step_lines: list[str] = []
    for step in script_state.steps:
        depends = ", ".join(step.depends_on) if step.depends_on else "none"
        step_lines.append(
            f"- [step_id: {step.step_id}] [status: {step.status}] [phase: {step.phase}] "
            f"[depends_on: {depends}] [source: {step.source}] {step.title} :: {step.instruction}"
        )

    return (
        f"## Task Summary\n{task_summary}\n\n"
        f"## Context\n{context}\n\n"
        f"## Execution Steps\n" + "\n".join(step_lines) + "\n\n"
        f"## Planner Hints\n{hint_section}\n\n"
        f"## Query Appendix\n{query_appendix}"
    ).strip()
