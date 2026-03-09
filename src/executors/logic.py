"""
LogicRunner - 逻辑运行器
使用 asteval 执行表达式，支持完整 Python 语法（if/else、变量赋值）
"""
from asteval import Interpreter

from ..types import LogicResult


class LogicRunner:
    """逻辑运行器 - 执行表达式"""
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
    
    def evaluate(self, expression: str, step_context: dict = None) -> LogicResult:
        """执行表达式"""
        if not expression or expression == "None":
            return LogicResult(success=True, result=None, resolved_paths={}, trace=[])
        
        try:
            # 获取当前状态
            state = self.state_manager.snapshot()
            
            # 替换 step_X_result 引用
            expr = expression
            if step_context:
                for key, value in step_context.items():
                    placeholder = f"{key}_result"
                    expr = expr.replace(placeholder, str(value))
            
            # 创建 interpreter
            interp = Interpreter()
            
            # 注入状态变量（展开为顶层变量）
            flat_state = self._flatten_state(state)
            interp.symtable.update(flat_state)
            
            # 执行表达式
            result = interp(expr)
            
            return LogicResult(
                success=len(interp.error) == 0,
                result=result,
                resolved_paths={},
                trace=[f"执行成功: {result}"]
            )
            
        except Exception as e:
            return LogicResult(
                success=False,
                result=None,
                resolved_paths={},
                trace=[f"执行失败: {e}"]
            )
    
    def _flatten_state(self, data: dict, prefix: str = "") -> dict:
        """将嵌套字典展开为点分隔的键值对"""
        items = {}
        for k, v in data.items():
            new_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                items.update(self._flatten_state(v, new_key))
            else:
                items[new_key] = v
        return items
