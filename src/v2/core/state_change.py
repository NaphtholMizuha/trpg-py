"""
状态变更记录
"""
from dataclasses import dataclass
from typing import Any


@dataclass
class StateChange:
    """状态变更记录"""
    path: str
    old_value: Any
    new_value: Any
    operation: str  # set, add, subtract
