from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, ValidationError

from augury.planner.dsl_template_catalog import (
    TaskFamily,
    ResolutionMode,
    ResourceMode,
    TargetingMode,
    SuccessRule,
    TemplateQuerySchema,
    build_invalid_template_query_result,
    query_template,
)


class TemplateInput(TemplateQuerySchema):
    pass


class TemplateTool(BaseTool):
    name: str = "template"
    description: str = (
        "按任务族查询合法 DSL 模板骨架、必填绑定项、绑定规则与常见错误。"
        "只读、无副作用，不执行任务也不写入状态。"
    )
    args_schema: type[BaseModel] = TemplateInput

    def invoke(self, input: Any, config: Any | None = None, **kwargs: Any) -> Any:
        try:
            return super().invoke(input, config=config, **kwargs)
        except ValidationError as exc:
            raw_query = _coerce_template_query_input(input)
            _log_template_input(**raw_query)
            result = build_invalid_template_query_result(raw_query, exc)
            _log_template_output(result)
            return result

    def _run(
        self,
        task_family: TaskFamily,
        resolution_mode: ResolutionMode = "unknown",
        resource_mode: ResourceMode = "unknown",
        targeting_mode: TargetingMode = "unknown",
        success_rule: SuccessRule = "unknown",
    ) -> dict[str, Any]:
        _log_template_input(
            task_family=task_family,
            resolution_mode=resolution_mode,
            resource_mode=resource_mode,
            targeting_mode=targeting_mode,
            success_rule=success_rule,
        )
        result = query_template(
            task_family=task_family,
            resolution_mode=resolution_mode,
            resource_mode=resource_mode,
            targeting_mode=targeting_mode,
            success_rule=success_rule,
        )
        _log_template_output(result)
        return result


def create_template_tool() -> TemplateTool:
    return TemplateTool()


def _coerce_template_query_input(input: Any) -> dict[str, Any]:
    raw_query = {
        "task_family": "unknown",
        "resolution_mode": "unknown",
        "resource_mode": "unknown",
        "targeting_mode": "unknown",
        "success_rule": "unknown",
    }
    if isinstance(input, dict):
        for field in raw_query:
            if field in input:
                raw_query[field] = input[field]
    return raw_query


def _log_template_input(
    *,
    task_family: Any,
    resolution_mode: Any,
    resource_mode: Any,
    targeting_mode: Any,
    success_rule: Any,
) -> None:
    logger.info(
        "tool_input tool=template task_family={!r} resolution_mode={!r} resource_mode={!r} targeting_mode={!r} success_rule={!r}",
        task_family,
        resolution_mode,
        resource_mode,
        targeting_mode,
        success_rule,
    )


def _log_template_output(result: dict[str, Any]) -> None:
    invalid_fields = [
        item.get("field")
        for item in result.get("invalid_fields", [])
        if isinstance(item, dict) and item.get("field") is not None
    ]
    logger.info(
        "tool_output tool=template status={} template_id={!r} fallback_used={} invalid_fields={!r}",
        result.get("status", "unknown"),
        result.get("template_id"),
        bool(result.get("fallback_used", False)),
        invalid_fields,
    )
