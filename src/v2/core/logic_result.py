"""
LogicRunner执行结果
"""
from dataclasses import dataclass
from typing import Any


@dataclass
class LogicResult:
    """LogicRunner执行结果"""
    success: bool
    result: Any
    resolved_paths: dict[str, Any]  # 解析的路径及实际值（用于审计）
    trace: list[str]                # 执行轨迹
