"""
执行计划相关数据类
"""
from dataclasses import dataclass
from typing import Any


@dataclass
class ExecutionStep:
    """执行步骤"""
    step_id: str
    description: str           # 步骤描述
    expression: str | None     # 逻辑表达式（如果有）
    condition: str | None      # 执行条件（如"命中时"）
    state_changes: list[dict]  # 计划的状态变更


@dataclass
class ExecutionPlan:
    """执行计划 - TaskAgent的输出"""
    task_id: str
    steps: list[ExecutionStep]
    required_rules: list[str]  # 需要查询的规则
