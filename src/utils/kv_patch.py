"""
KV 字段级补丁工具

将 KV Value 解析为字段，支持字段级修改
"""
import re
from typing import Any


class KVPatch:
    """KV 补丁应用器

    将格式 "字段1: 值1 | 字段2: 值2" 解析为可修改的字典
    """

    def __init__(self, full_value: str):
        """
        Args:
            full_value: 完整的 KV Value，如 "HP: 44/44 | AC: 18"
        """
        self.full_value = full_value
        self.fields = self._parse(full_value)

    def _parse(self, value: str) -> dict[str, str]:
        """解析完整值为字段字典"""
        fields = {}
        if not value or value.strip() == "":
            return fields

        # 按 | 分割字段
        parts = value.split("|")
        for part in parts:
            part = part.strip()
            if ":" in part:
                # 第一个冒号作为分隔符
                key, val = part.split(":", 1)
                fields[key.strip()] = val.strip()
        return fields

    def get_field(self, field: str) -> str | None:
        """获取字段值"""
        return self.fields.get(field)

    def set_field(self, field: str, value: str) -> "KVPatch":
        """设置字段值"""
        self.fields[field] = value
        return self

    def remove_field(self, field: str) -> "KVPatch":
        """删除字段"""
        if field in self.fields:
            del self.fields[field]
        return self

    def to_string(self) -> str:
        """序列化为完整值"""
        if not self.fields:
            return ""
        parts = [f"{k}: {v}" for k, v in self.fields.items()]
        return " | ".join(parts)

    def has_field(self, field: str) -> bool:
        """检查字段是否存在"""
        return field in self.fields


def apply_field_change(store, change: dict[str, Any]) -> tuple[str, str]:
    """应用字段级变更到 KVStore

    Args:
        store: KVStateStore 实例
        change: 变更指令，格式 {"key": "...", "field": "...", "new_value": "..."}

    Returns:
        (old_full_value, new_full_value) 元组
    """
    key = change["key"]
    field = change["field"]
    new_value = change["new_value"]

    # 读取当前完整值
    current_full = store.get(key) or ""

    # 应用补丁
    patch = KVPatch(current_full)
    patch.set_field(field, new_value)
    new_full = patch.to_string()

    # 写回
    store.set(key, new_full)

    return current_full, new_full
