"""
V2 执行器 - LogicRunner 和 StateWriter
"""
import random
import re
from typing import Any
from .types import LogicResult, StateChange


class LogicRunner:
    """逻辑运行器 - 执行表达式，解析路径获取实际值"""
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
    
    def evaluate(self, expression: str, step_context: dict = None) -> LogicResult:
        """
        执行表达式
        
        Args:
            expression: 表达式字符串，如 "Roll('1d20') + entity.players.player_01.attributes.strength"
            step_context: 前序步骤的结果，用于条件判断
        """
        if not expression or expression == "None":
            return LogicResult(success=True, result=None, resolved_paths={}, trace=[])
        
        trace = []
        resolved_paths = {}
        
        try:
            # 解析并执行 Roll 函数
            expr = expression
            
            # 找出所有 Roll 调用
            roll_pattern = r"Roll\('(\d+)d(\d+)'\)"
            
            def do_roll(match):
                num = int(match.group(1))
                sides = int(match.group(2))
                results = [random.randint(1, sides) for _ in range(num)]
                total = sum(results)
                trace.append(f"Roll('{num}d{sides}') = {results} = {total}")
                return str(total)
            
            expr = re.sub(roll_pattern, do_roll, expr)
            
            # 解析路径引用 - 替换为实际值
            # 路径格式：entity.xxx.yyy.zzz
            path_pattern = r"entity\.[a-zA-Z_][a-zA-Z0-9_\[\].]*"
            
            def resolve_path(match):
                path = match.group(0)
                try:
                    value = self.state_manager.get(path)
                    resolved_paths[path] = value
                    trace.append(f"{path} = {value}")
                    return str(value)
                except Exception as e:
                    trace.append(f"{path} 解析失败: {e}")
                    return "0"
            
            expr = re.sub(path_pattern, resolve_path, expr)
            
            # 解析 step_X_result 引用
            if step_context:
                step_pattern = r"step_(\d+)_result"
                
                def resolve_step(match):
                    step_idx = int(match.group(1))
                    key = f"step_{step_idx}"
                    if key in step_context:
                        value = step_context[key]
                        trace.append(f"step_{step_idx}_result = {value}")
                        return str(value)
                    return "0"
                
                expr = re.sub(step_pattern, resolve_step, expr)
            
            # 安全执行表达式
            trace.append(f"计算: {expr}")
            
            # 只允许安全的运算符
            allowed_chars = set("0123456789+-*/.()<>=! ")
            if not all(c in allowed_chars for c in expr):
                raise ValueError(f"表达式包含非法字符: {expr}")
            
            result = eval(expr)
            trace.append(f"结果: {result}")
            
            return LogicResult(
                success=True,
                result=result,
                resolved_paths=resolved_paths,
                trace=trace
            )
            
        except Exception as e:
            trace.append(f"执行失败: {e}")
            return LogicResult(
                success=False,
                result=None,
                resolved_paths=resolved_paths,
                trace=trace
            )


class StateWriter:
    """状态写入器 - 唯一可直接修改世界状态的组件"""
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.change_log: list[StateChange] = []
    
    def apply_changes(self, changes: list[dict], step_results: dict) -> list[StateChange]:
        """
        应用状态变更
        
        Args:
            changes: 变更列表，每个包含 path, operation, value_expr
            step_results: 步骤结果，用于解析 value_expr
        """
        applied = []
        
        for change in changes:
            path = change["path"]
            operation = change["operation"]
            value_expr = change.get("value_expr")
            
            try:
                # 获取旧值
                try:
                    old_value = self.state_manager.get(path)
                except:
                    old_value = None
                
                # 解析新值
                if value_expr is None:
                    new_value = None
                elif value_expr.startswith("'") and value_expr.endswith("'"):
                    # 字符串字面量
                    new_value = value_expr[1:-1]
                elif value_expr.startswith("step_") and "_result" in value_expr:
                    # 引用步骤结果
                    step_key = value_expr.replace("_result", "")
                    new_value = step_results.get(step_key)
                else:
                    try:
                        new_value = int(value_expr)
                    except:
                        new_value = value_expr
                
                # 执行操作
                if operation == "set":
                    self.state_manager.set(path, new_value)
                elif operation == "subtract":
                    if old_value is not None and new_value is not None:
                        new_value = old_value - new_value
                        self.state_manager.set(path, new_value)
                elif operation == "add":
                    if old_value is not None and new_value is not None:
                        new_value = old_value + new_value
                        self.state_manager.set(path, new_value)
                
                # 记录变更
                state_change = StateChange(
                    path=path,
                    old_value=old_value,
                    new_value=new_value,
                    operation=operation
                )
                self.change_log.append(state_change)
                applied.append(state_change)
                
            except Exception as e:
                print(f"  ⚠️  变更失败 {path}: {e}")
        
        return applied
    
    def get_change_log(self) -> list[StateChange]:
        """获取变更日志"""
        return self.change_log.copy()
    
    def clear_log(self):
        """清空日志"""
        self.change_log.clear()
