"""
StateWriter - 状态写入器
使用StateManager执行状态变更
"""
from typing import Any

from ..types import StateChange


class StateWriter:
    """状态写入器 - 唯一可直接修改世界状态的组件"""
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.change_log: list[StateChange] = []
    
    def apply_changes(self, changes: list[dict], step_results: dict) -> list[StateChange]:
        """应用状态变更"""
        applied = []
        
        for change in changes:
            path = change["path"]
            operation = change["operation"]
            value_expr = change.get("value_expr")
            
            try:
                # 获取旧值
                try:
                    old_value = self.state_manager.get(path)
                except KeyError:
                    old_value = None
                
                # 解析新值
                new_value = self._resolve_value(value_expr, step_results)
                
                # 执行操作
                if operation == "set":
                    self.state_manager.set(path, new_value)
                elif operation == "subtract":
                    new_value = self.state_manager.subtract(path, new_value)
                elif operation == "add":
                    new_value = self.state_manager.add(path, new_value)
                
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
    
    def _resolve_value(self, value_expr, step_results: dict) -> Any:
        """解析值表达式"""
        if value_expr is None:
            return None
        
        if isinstance(value_expr, str):
            # 字符串字面量
            if value_expr.startswith("'") and value_expr.endswith("'"):
                return value_expr[1:-1]
            
            # 步骤结果引用
            if value_expr.startswith("step_") and "_result" in value_expr:
                step_key = value_expr.replace("_result", "")
                return step_results.get(step_key)
            
            # 尝试转为数字
            try:
                return int(value_expr)
            except ValueError:
                try:
                    return float(value_expr)
                except ValueError:
                    return value_expr
        
        return value_expr
    
    def get_change_log(self) -> list[StateChange]:
        """获取变更日志"""
        return self.change_log.copy()
    
    def clear_log(self):
        """清空日志"""
        self.change_log.clear()
