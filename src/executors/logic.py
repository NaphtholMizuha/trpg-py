"""
LogicRunner - 逻辑运行器
使用 LogicEngine 执行表达式，支持详细计算轨迹
"""
from ..tools.logic import LogicEngine, EvalResult


class LogicRunner:
    """逻辑运行器 - 执行表达式"""

    def __init__(self, logic_engine: LogicEngine | None = None):
        self.logic_engine = logic_engine or LogicEngine()

    def evaluate(self, expression: str, step_context: dict | None = None) -> EvalResult:
        """执行表达式，返回详细计算轨迹"""
        if not expression or expression == "None":
            return EvalResult(success=True, result=None, resolved="无表达式")

        try:
            # 使用 LogicEngine 执行，获取详细轨迹
            eval_result = self.logic_engine.eval(expression)

            return EvalResult(
                success=True,
                result=eval_result.result,
                resolved=eval_result.resolved
            )

        except Exception as e:
            return EvalResult(
                success=False,
                result=None,
                resolved=f"执行失败: {e}"
            )
