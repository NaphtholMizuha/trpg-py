"""
任务意图 - InterfaceAgent的输出
"""
from dataclasses import dataclass, field
from .enums import TaskType


@dataclass
class TaskIntent:
    """任务意图"""
    task_id: str
    description: str           # 任务描述
    task_type: TaskType        # 任务类型
    actor: str                 # 行动者实体ID或名称
    target: str | None         # 目标实体ID或名称
    action: str                # 具体动作
    context: dict = field(default_factory=dict)  # 额外上下文
