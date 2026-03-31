from augury.planner.nodes.task_node import TaskNode, TaskNodeDependencies

# Temporary compatibility alias while call sites migrate to task_node.
IntentNode = TaskNode
IntentNodeDependencies = TaskNodeDependencies

__all__ = [
    "IntentNode",
    "IntentNodeDependencies",
    "TaskNode",
    "TaskNodeDependencies",
]
