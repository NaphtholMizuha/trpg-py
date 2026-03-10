"""
LogicRunner - 逻辑运行器
使用 LogicEngine 执行表达式，支持详细计算轨迹
"""
from ..types import LogicResult
from ..tools.logic import LogicEngine


class LogicRunner:
    """逻辑运行器 - 执行表达式"""

    def __init__(self, logic_engine: LogicEngine | None = None):
        self.logic_engine = logic_engine or LogicEngine()

    def evaluate(self, expression: str, step_context: dict | None = None) -> LogicResult:
        """执行表达式，返回详细计算轨迹"""
        if not expression or expression == "None":
            return LogicResult(success=True, result=None, resolved_paths={}, trace=[])

        try:
            # 准备上下文变量
            context = step_context or {}

            # 使用 LogicEngine 执行，获取详细轨迹
            eval_result = self.logic_engine.eval(expression, context)

            return LogicResult(
                success=True,
                result=eval_result.result,
                resolved_paths={},
                trace=[eval_result.resolved]  # 使用详细的解析轨迹
            )

        except Exception as e:
            return LogicResult(
                success=False,
                result=None,
                resolved_paths={},
                trace=[f"执行失败: {e}"]
            )
