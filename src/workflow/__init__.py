"""
Workflow - 工作流层 (V11版本 - 混合堆栈架构)

核心特性:
1. 主流程使用队列 (FIFO) 管理用户任务
2. 执行阶段使用堆栈 (LIFO) 处理反应和连锁
3. 使用 interrupt 替代 input() 阻塞调用
4. 使用 Command(goto=...) 替代条件边路由
5. 节点返回 Command 直接控制流程
"""
from .graph import create_workflow
from .nodes import (
    create_planner_node,
    create_executor_node,  # 保留作为备用
    create_dm_decision_node,
    create_context_builder_node,
    create_decision_point_node,
    create_resolution_builder_node,
    create_resolution_runner_node,
)

__all__ = [
    "create_workflow",
    "create_planner_node",
    "create_executor_node",
    "create_dm_decision_node",
    "create_context_builder_node",
    "create_decision_point_node",
    "create_resolution_builder_node",
    "create_resolution_runner_node",
]
