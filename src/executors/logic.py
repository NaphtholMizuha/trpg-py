"""
LogicRunner - 逻辑运行器
使用 LogicEngine 执行表达式，支持详细计算轨迹
"""
from ..types import LogicResult
from ..tools.logic import LogicEngine


class LogicRunner:
    """逻辑运行器 - 执行表达式"""
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.logic_engine = LogicEngine()
    
    def evaluate(self, expression: str, step_context: dict = None) -> LogicResult:
        """执行表达式，返回详细计算轨迹"""
        if not expression or expression == "None":
            return LogicResult(success=True, result=None, resolved_paths={}, trace=[])
        
        try:
            # 获取当前状态
            state = self.state_manager.snapshot()
            
            # 替换 step_X_result 引用为实际值（在表达式中）
            expr = expression
            if step_context:
                for key, value in step_context.items():
                    placeholder = f"{key}_result"
                    # 将值注入到状态中，让表达式可以引用
                    state[placeholder] = value
            
            # 使用 LogicEngine 执行，获取详细轨迹
            eval_result = self.logic_engine.eval(expr, state)
            
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
