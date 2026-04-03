from __future__ import annotations

from typing import Any, Literal

from langchain_core.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field, ValidationError as PydanticValidationError

from augury.planner.dsl_shape_catalog import build_expected_shape
from augury.planner.task_document import validate_candidate_task_document
from augury.errors import ValidationError


class LintIssue(BaseModel):
    path: str = ""
    message: str
    code: str | None = None
    expected: dict[str, Any] | None = None


class LintError(BaseModel):
    type: str
    message: str


class LintResult(BaseModel):
    status: Literal["valid", "invalid", "error"]
    summary: str | None = None
    issues: list[LintIssue] = Field(default_factory=list)
    error: LintError | None = None


class LintInput(BaseModel):
    task_document: dict[str, Any]


class LintTool(BaseTool):
    name: str = "lint"
    description: str = (
        "校验候选 TaskDocument 是否满足当前引擎 DSL 的结构和语义约束。"
        "只读、无副作用，不执行任务也不写入状态。"
    )
    args_schema: type[BaseModel] = LintInput

    def _run(self, task_document: dict[str, Any]) -> dict[str, Any]:
        _log_lint_input(task_document=task_document)
        try:
            result = lint_task_document(task_document)
        except Exception as exc:
            result = LintResult(
                status="error",
                error=LintError(type=exc.__class__.__name__, message=str(exc)),
            )
        _log_lint_output(result)
        return result.model_dump(exclude_none=True)


def lint_task_document(task_document: dict[str, Any]) -> LintResult:
    try:
        validate_candidate_task_document(task_document)
    except PydanticValidationError as exc:
        issues = [
            LintIssue(
                path=_format_error_path(error.get("loc", ())),
                message=str(error.get("msg", "")),
                code=str(error.get("type")) if error.get("type") is not None else None,
            )
            for error in exc.errors()
        ]
        issues = _attach_expected_shapes(task_document, issues)
        return LintResult(status="invalid", summary=str(exc), issues=issues)
    except ValidationError as exc:
        issues = [
            LintIssue(
                path=str(issue.get("path", "")),
                message=str(issue.get("message", str(exc))),
                code=str(issue.get("code")) if issue.get("code") is not None else None,
                expected=_extract_issue_expected(issue),
            )
            for issue in getattr(exc, "issues", [])
        ]
        if not issues:
            issues = [LintIssue(message=str(exc), code=exc.__class__.__name__)]
        issues = _attach_expected_shapes(task_document, issues)
        return LintResult(
            status="invalid",
            summary=str(exc),
            issues=issues,
        )
    except (ValueError, TypeError) as exc:
        return LintResult(
            status="invalid",
            summary=str(exc),
            issues=[LintIssue(message=str(exc), code=exc.__class__.__name__)],
        )
    return LintResult(status="valid", summary="TaskDocument is valid.")


def create_lint_tool() -> LintTool:
    return LintTool()


def _format_error_path(location: tuple[Any, ...] | list[Any]) -> str:
    parts: list[str] = []
    for item in location:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, int):
            parts.append(str(item))
        else:
            parts.append(str(item))
    return ".".join(parts)


def _attach_expected_shapes(
    task_document: dict[str, Any],
    issues: list[LintIssue],
) -> list[LintIssue]:
    enriched: list[LintIssue] = []
    for issue in issues:
        if issue.expected is not None:
            enriched.append(issue)
            continue
        expected = _infer_expected_shape(task_document, issue.path)
        if expected is None:
            enriched.append(issue)
            continue
        enriched.append(issue.model_copy(update={"expected": expected}))
    return enriched


def _infer_expected_shape(task_document: dict[str, Any], path: str) -> dict[str, Any] | None:
    if not isinstance(path, str) or not path.startswith("steps."):
        return None
    parts = path.split(".")
    if len(parts) < 2 or not parts[1].isdigit():
        return None
    steps = task_document.get("steps")
    if not isinstance(steps, list):
        return None
    index = int(parts[1])
    if index < 0 or index >= len(steps):
        return None
    raw_step = steps[index]
    if not isinstance(raw_step, dict):
        return None
    step_type = raw_step.get("type")
    step_kind = raw_step.get("kind")
    if not isinstance(step_type, str) or not isinstance(step_kind, str):
        return None
    return build_expected_shape(step_type, step_kind)


def _extract_issue_expected(issue: dict[str, Any]) -> dict[str, Any] | None:
    expected = issue.get("expected")
    return expected if isinstance(expected, dict) else None


def _log_lint_input(*, task_document: dict[str, Any]) -> None:
    logger.info(
        "tool_input tool=lint task_id={!r} steps={}",
        task_document.get("task_id"),
        len(task_document.get("steps", [])) if isinstance(task_document.get("steps"), list) else 0,
    )


def _log_lint_output(result: LintResult) -> None:
    if result.status == "valid":
        logger.info("tool_output tool=lint status=valid")
        return
    if result.status == "invalid":
        logger.info(
            "tool_output tool=lint status=invalid issues={} sample_paths={}",
            len(result.issues),
            [issue.path for issue in result.issues[:3]],
        )
        return
    logger.error(
        "tool_output tool=lint status=error error_type={} error_message={!r}",
        result.error.type if result.error else "unknown",
        result.error.message if result.error else "",
    )
