"""
连锁触发条件
"""
from dataclasses import dataclass


@dataclass
class ChainTrigger:
    """连锁触发条件"""
    condition: str      # 触发条件表达式
    effect: str         # 效果描述
    priority: int       # 优先级
