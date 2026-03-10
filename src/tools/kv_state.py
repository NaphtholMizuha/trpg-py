"""
KVStateStore - 极简 KV 文本存储
状态 = 纯 KV 文本文件，LLM 直接读写文本
"""

import re
import fcntl
import os
from dataclasses import dataclass


@dataclass
class KVChange:
    """KV 状态变更记录"""
    key: str
    old_value: str | None
    new_value: str | None
    operation: str


class KVStateStore:
    """极简 KV 文本存储

    world_state.txt 格式:
    [Key] Value

    其中 Value 是完整的自然语言段落，不是单个字段

    示例:
    [Aldera.combat] HP: 44/44 | 临时HP: 0 | AC: 18 (链甲16+盾牌2) | 先攻调整值: +1
    [Aldera.abilities] 力量 16 (+3) 豁免+6(熟练) | 敏捷 12 (+1) 豁免+1 | ...
    """

    def __init__(self, filepath: str, persist: bool = False):
        self.filepath = filepath
        self._data: dict[str, str] = {}
        self.persist = persist  # 是否持久化到文件
        self._load()

    def _load(self) -> None:
        """解析 world_state.txt 为 dict"""
        if not os.path.exists(self.filepath):
            self._data = {}
            return

        with open(self.filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        self._data = self._parse(content)

    def _parse(self, content: str) -> dict[str, str]:
        """解析文本内容为 dict

        格式: [Key] Value
        Value 可以跨越多行，直到下一个 [Key] 或文件结束
        """
        data: dict[str, str] = {}

        # 匹配 [Key] 模式，支持跨行 Value
        pattern = r'^\[([^\]]+)\]\s*(.*?)(?=\n\[|\Z)'
        matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)

        for match in matches:
            key = match.group(1).strip()
            value = match.group(2).strip()
            data[key] = value

        return data

    def _save(self) -> None:
        """保存 dict 到 world_state.txt"""
        # 确保目录存在
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)

        # 构建文本内容
        lines = []
        for key, value in sorted(self._data.items()):
            lines.append(f"[{key}] {value}")
            lines.append("")  # 空行分隔

        content = "\n".join(lines)

        # 使用文件锁保证并发安全
        with open(self.filepath, 'w', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(content)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def get_text(self) -> str:
        """返回完整文本给 LLM"""
        if not self._data:
            return "[世界状态为空]"

        lines = []
        for key, value in sorted(self._data.items()):
            lines.append(f"[{key}] {value}")

        return "\n".join(lines)

    def get(self, key: str) -> str | None:
        """获取单个 key 的值"""
        return self._data.get(key)

    def get_by_prefix(self, prefix: str) -> dict[str, str]:
        """获取匹配前缀的所有 key-value"""
        return {k: v for k, v in self._data.items() if k.startswith(prefix)}

    def patch(self, operations: list[dict]) -> tuple[bool, list[KVChange]]:
        """
        执行操作列表

        operations: [
            {"op": "ADD", "key": "Aldera.combat", "value": "HP: 44/44 | AC: 18 ..."},
            {"op": "MOD", "key": "Goblin.combat", "value": "HP: 4/10 | AC: 15 ..."},
            {"op": "DEL", "key": "Temp.status"}
        ]

        Returns:
            (success, change_log)
        """
        change_log: list[KVChange] = []

        try:
            for op in operations:
                operation = op.get("op", "").upper()
                key = op.get("key", "")
                value = op.get("value", "")

                if not key:
                    continue

                if operation == "ADD":
                    old = self._data.get(key)
                    if old is not None:
                        # 如果已存在，改为 MOD
                        operation = "MOD"
                    else:
                        self._data[key] = value
                        change_log.append(KVChange(key, old, value, "ADD"))

                if operation == "MOD":
                    old = self._data.get(key)
                    self._data[key] = value
                    change_log.append(KVChange(key, old, value, "MOD"))

                elif operation == "DEL":
                    old = self._data.pop(key, None)
                    if old is not None:
                        change_log.append(KVChange(key, old, None, "DEL"))

            # 只在启用持久化时保存到文件
            if self.persist:
                self._save()
            return True, change_log

        except Exception:
            return False, change_log

    def get_all_keys(self) -> list[str]:
        """获取所有 key 列表"""
        return list(self._data.keys())

    def get_keys(self) -> list[str]:
        """获取所有 key 列表（别名）"""
        return self.get_all_keys()

    def get_multi(self, keys: list[str]) -> dict[str, str]:
        """批量获取多个key的value"""
        return {k: self._data.get(k) for k in keys if k in self._data}

    def reload(self) -> None:
        """重新加载文件（用于外部修改后）"""
        self._load()

    def to_dict(self) -> dict[str, str]:
        """导出为 dict（用于调试）"""
        return self._data.copy()
