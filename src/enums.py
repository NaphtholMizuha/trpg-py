"""
核心枚举类型
"""
from enum import Enum


class TaskType(Enum):
    """任务类型"""
    ATTACK = "attack"           # 物理攻击
    SPELL = "spell"             # 法术
    INTERACT = "interact"       # 环境互动
    MOVE = "move"               # 移动
