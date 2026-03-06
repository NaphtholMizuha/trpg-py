import json
from typing import Any
from glom import glom, assign, delete, PathAccessError, T, Spec

class StateManager:
    """基于 glom 的状态管理器，支持点分隔路径访问（无锁版本）"""

    def __init__(self, initial: dict[str, Any] | None = None):
        self._state: dict[str, Any] = dict(initial) if initial else {}

    # --- 查询 ---

    def get(self, path: str) -> Any:
        try:
            return glom(self._state, path)
        except PathAccessError:
            raise KeyError(f"路径不存在: {path}")
            
    def get_schema(self) -> Any:
        def _type_schema(value):
            if isinstance(value, dict):
                return {k: _type_schema(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [_type_schema(value[0])] if value else []
            elif isinstance(value, tuple):
                return tuple(_type_schema(v) for v in value)
            elif isinstance(value, set):
                return {_type_schema(next(iter(value)))} if value else set()
            else:
                return type(value).__name__

        return _type_schema(self._state)

    def get_or(self, path: str, default: Any = None) -> Any:
        # glom 的 get 模式可以在路径不存在时返回默认值
        return glom(self._state, path, default=default)

    def exists(self, path: str) -> bool:
        try:
            glom(self._state, path)
            return True
        except PathAccessError:
            return False

    # --- 修改 ---

    def set(self, path: str, value: Any) -> None:
        # missing=dict 确保中间路径不存在时自动创建字典
        assign(self._state, path, value, missing=dict)

    # --- 数值操作 ---

    def add(self, path: str, delta: int | float) -> int | float:
        val = self.get(path)
        if not isinstance(val, (int, float)):
            raise TypeError(f"路径 {path} 的值不是数值: {type(val)}")
        new_val = val + delta
        self.set(path, new_val)
        return new_val

    def subtract(self, path: str, delta: int | float) -> int | float:
        return self.add(path, -delta)

    def multiply(self, path: str, factor: int | float) -> int | float:
        val = self.get(path)
        new_val = val * factor
        self.set(path, new_val)
        return new_val

    def divide(self, path: str, divisor: int | float) -> float:
        if divisor == 0: 
            raise ZeroDivisionError("除数不能为零")
        val = self.get(path)
        new_val = val / divisor
        self.set(path, new_val)
        return new_val

    # --- 删除 ---

    def delete(self, path: str) -> Any:
        val = self.get(path)
        delete(self._state, path)
        return val

    # --- 批量操作 ---

    def update(self, data: dict[str, Any]) -> None:
        # 深度合并：将 data 的内容合并进 _state
        for key, value in data.items():
            assign(self._state, key, value, missing=dict)

    def clear(self) -> None:
        self._state.clear()

    def snapshot(self) -> dict[str, Any]:
        return json.loads(json.dumps(self._state))

    def to_json(self) -> str:
        return json.dumps(self._state, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "StateManager":
        return cls(json.loads(json_str))

    # --- 魔术方法 ---

    def __contains__(self, path: str) -> bool:
        return self.exists(path)

    def __getitem__(self, path: str) -> Any:
        return self.get(path)

    def __setitem__(self, path: str, value: Any) -> None:
        self.set(path, value)

    def __delitem__(self, path: str) -> None:
        self.delete(path)

    def __repr__(self) -> str:
        return f"StateManager({self._state})"