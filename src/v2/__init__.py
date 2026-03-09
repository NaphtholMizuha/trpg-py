"""
TRPG Agent V2 - 多Agent协作架构

目录结构：
- core/: 核心类型定义
- agents/: Agent实现
- executors/: 执行器实现
- workflow/: LangGraph工作流
"""

# Core
from .core import (
    TaskType,
    TaskIntent,
    RelevantPaths,
    ExecutionStep,
    ExecutionPlan,
    LogicResult,
    StateChange,
    ChainTrigger,
    AgentState,
)

# Agents
from .agents import (
    InterfaceAgent,
    LLMStateSummarizer,
    TaskAgent,
    ChainAgent,
)

# Executors
from .executors import (
    LogicRunner,
    StateWriter,
)

# Workflow
from .workflow import create_workflow

__all__ = [
    # Core
    "TaskType",
    "TaskIntent",
    "RelevantPaths",
    "ExecutionStep",
    "ExecutionPlan",
    "LogicResult",
    "StateChange",
    "ChainTrigger",
    "AgentState",
    # Agents
    "InterfaceAgent",
    "LLMStateSummarizer",
    "TaskAgent",
    "ChainAgent",
    # Executors
    "LogicRunner",
    "StateWriter",
    # Workflow
    "create_workflow",
]
