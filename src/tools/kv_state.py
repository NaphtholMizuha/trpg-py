from __future__ import annotations

"""
KVStateStore - 支持 txt / toml 的扁平 KV 存储
"""

import fcntl
import os
import re
import tomllib
from dataclasses import dataclass


@dataclass
class KVChange:
    """KV 状态变更记录"""

    key: str
    old_value: str | None
    new_value: str | None
    operation: str


class KVStateStore:
    """极简 KV 存储

    支持两种磁盘格式：
    1. 旧版 txt: [Key] Value
    2. 新版 toml: 嵌套表结构

    运行时统一暴露扁平 key，例如 `Aldera.combat`。
    """

    def __init__(self, filepath: str | None = None, persist: bool = False):
        self.filepath = filepath or "/tmp/world_state.txt"
        self._data: dict[str, str] = {}
        self.persist = persist
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.filepath):
            self._data = {}
            return

        if self.filepath.endswith(".toml"):
            with open(self.filepath, "rb") as f:
                content = tomllib.load(f)
            self._data = self._flatten_tree(content)
            return

        with open(self.filepath, "r", encoding="utf-8") as f:
            content = f.read()
        self._data = self._parse_legacy_text(content)

    def _parse_legacy_text(self, content: str) -> dict[str, str]:
        data: dict[str, str] = {}
        pattern = r"^\[([^\]]+)\]\s*(.*?)(?=\n\[|\Z)"
        matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
        for match in matches:
            key = match.group(1).strip()
            value = match.group(2).strip()
            data[key] = value
        return data

    def _flatten_tree(self, data: dict, prefix: str = "") -> dict[str, str]:
        flat: dict[str, str] = {}
        for key, value in data.items():
            current = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                summary = value.get("summary")
                if summary is not None:
                    flat[current] = str(summary)
                flat.update(self._flatten_tree(value, current))
            else:
                flat[current] = str(value)
        return flat

    def _unflatten_tree(self) -> dict[str, object]:
        tree: dict[str, object] = {}
        for dotted_key, value in sorted(self._data.items()):
            parts = dotted_key.split(".")
            current = tree
            for part in parts[:-1]:
                child = current.get(part)
                if child is None:
                    child = {}
                    current[part] = child
                elif not isinstance(child, dict):
                    child = {"summary": child}
                    current[part] = child
                current = child
            existing = current.get(parts[-1])
            if isinstance(existing, dict):
                existing["summary"] = value
            else:
                current[parts[-1]] = value
        return tree

    def _dump_toml(self, data: dict[str, object], parent: str = "") -> str:
        root_scalars, sections = self._collect_toml_sections(data, parent)
        blocks: list[str] = []
        if root_scalars:
            blocks.append("\n".join(root_scalars))
        for section_name, scalar_lines in sections:
            lines = [f"[{section_name}]"]
            lines.extend(scalar_lines)
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    def _collect_toml_sections(
        self,
        data: dict[str, object],
        parent: str = "",
    ) -> tuple[list[str], list[tuple[str, list[str]]]]:
        scalar_lines: list[str] = []
        child_sections: list[tuple[str, list[str]]] = []

        for key, value in data.items():
            if isinstance(value, dict):
                child_parent = f"{parent}.{key}" if parent else key
                _, nested_sections = self._collect_toml_sections(value, child_parent)
                child_sections.extend(nested_sections)
            else:
                escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
                scalar_lines.append(f'{key} = "{escaped}"')

        if parent:
            return [], [(parent, scalar_lines), *child_sections]
        return scalar_lines, child_sections

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)

        if self.filepath.endswith(".toml"):
            content = self._dump_toml(self._unflatten_tree()) + "\n"
        else:
            lines = []
            for key, value in sorted(self._data.items()):
                lines.append(f"[{key}] {value}")
                lines.append("")
            content = "\n".join(lines)

        with open(self.filepath, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(content)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def get_text(self) -> str:
        if not self._data:
            return "[世界状态为空]"

        lines = []
        for key, value in sorted(self._data.items()):
            lines.append(f"[{key}] {value}")
        return "\n".join(lines)

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value
        if self.persist:
            self._save()

    def get_by_prefix(self, prefix: str) -> dict[str, str]:
        return {k: v for k, v in self._data.items() if k.startswith(prefix)}

    def patch(self, operations: list[dict]) -> tuple[bool, list[KVChange]]:
        change_log: list[KVChange] = []
        try:
            touched_keys: set[str] = set()
            for op in operations:
                operation = op.get("op", "").upper()
                key = op.get("key", "")
                value = op.get("value", "")

                if not key:
                    continue

                if operation == "ADD":
                    old = self._data.get(key)
                    if old is not None:
                        operation = "MOD"
                    else:
                        self._data[key] = value
                        touched_keys.add(key)
                        change_log.append(KVChange(key, old, value, "ADD"))

                if operation == "MOD":
                    old = self._data.get(key)
                    self._data[key] = value
                    touched_keys.add(key)
                    change_log.append(KVChange(key, old, value, "MOD"))

                elif operation == "DEL":
                    old = self._data.pop(key, None)
                    if old is not None:
                        touched_keys.add(key)
                        change_log.append(KVChange(key, old, None, "DEL"))

            self._refresh_derived_summaries(touched_keys)

            if self.persist:
                self._save()
            return True, change_log
        except Exception:
            return False, change_log

    def get_all_keys(self) -> list[str]:
        return list(self._data.keys())

    def get_keys(self) -> list[str]:
        return self.get_all_keys()

    def get_multi(self, keys: list[str]) -> dict[str, str]:
        return {k: self._data.get(k) for k in keys if k in self._data}

    def reload(self) -> None:
        self._load()

    def to_dict(self) -> dict[str, str]:
        return self._data.copy()

    def _refresh_derived_summaries(self, touched_keys: set[str]) -> None:
        parent_keys: set[str] = set()
        for key in touched_keys:
            if key.count(".") >= 2:
                parent_keys.add(key.rsplit(".", 1)[0])

        for parent_key in parent_keys:
            summary = self._build_summary(parent_key)
            if summary is not None:
                self._data[parent_key] = summary

    def _build_summary(self, parent_key: str) -> str | None:
        if parent_key.endswith(".combat"):
            return self._build_combat_summary(parent_key)
        if parent_key.endswith(".equipment"):
            return self._build_equipment_summary(parent_key)
        if parent_key.endswith(".spell_slots"):
            return self._build_spell_slots_summary(parent_key)
        return None

    def _build_combat_summary(self, parent_key: str) -> str | None:
        hp_current = self.get(f"{parent_key}.hp_current")
        hp_max = self.get(f"{parent_key}.hp_max")
        temp_hp = self.get(f"{parent_key}.temp_hp")
        ac = self.get(f"{parent_key}.ac")
        ac_detail = self.get(f"{parent_key}.ac_detail")
        initiative = self.get(f"{parent_key}.initiative_mod")
        speed = self.get(f"{parent_key}.speed")
        hit_dice = self.get(f"{parent_key}.hit_dice")
        hit_dice_remaining = self.get(f"{parent_key}.hit_dice_remaining")
        status = self.get(f"{parent_key}.status")
        position = self.get(f"{parent_key}.position")
        reaction = self.get(f"{parent_key}.reaction")
        bonus_action = self.get(f"{parent_key}.bonus_action")
        cover = self.get(f"{parent_key}.cover")

        if not any((hp_current, hp_max, ac, status, position)):
            return None

        parts: list[str] = []
        if hp_current and hp_max:
            parts.append(f"HP: {hp_current}/{hp_max}")
        elif hp_current:
            parts.append(f"HP: {hp_current}")
        if temp_hp is not None:
            parts.append(f"临时HP: {temp_hp}")
        if ac:
            ac_text = f"AC: {ac}"
            if ac_detail:
                ac_text += f" ({ac_detail})"
            parts.append(ac_text)
        if initiative is not None:
            parts.append(f"先攻调整值: {initiative}")
        if speed:
            parts.append(f"速度: {speed}")
        if hit_dice:
            hit_dice_text = hit_dice
            if hit_dice_remaining is not None:
                hit_dice_text += f" ({hit_dice_remaining}剩余)"
            parts.append(f"生命骰: {hit_dice_text}")
        if status:
            parts.append(f"状态: {status}")
        if position:
            parts.append(f"位置: {position}")
        if reaction:
            parts.append(f"反应: {reaction}")
        if bonus_action:
            parts.append(f"附赠动作: {bonus_action}")
        if cover:
            parts.append(f"掩体: {cover}")
        return " | ".join(parts)

    def _build_equipment_summary(self, parent_key: str) -> str | None:
        order = [
            ("main_hand", "主手"),
            ("off_hand", "副手"),
            ("armor", "护甲"),
            ("ring", "戒指"),
            ("amulet", "护符"),
            ("accessory", "饰品"),
            ("ranged", "远程"),
            ("other", "其他"),
        ]
        parts: list[str] = []
        for field, label in order:
            value = self.get(f"{parent_key}.{field}")
            if value:
                parts.append(f"{label}: {value}")
        return " | ".join(parts) if parts else None

    def _build_spell_slots_summary(self, parent_key: str) -> str | None:
        parts: list[str] = []
        levels = sorted(
            {
                match.group(1)
                for key in self._data
                for match in [re.fullmatch(rf"{re.escape(parent_key)}\.level_(\d+)_(current|max)", key)]
                if match
            },
            key=int,
        )
        for level in levels:
            current = self.get(f"{parent_key}.level_{level}_current")
            max_value = self.get(f"{parent_key}.level_{level}_max")
            if current is not None and max_value is not None:
                parts.append(f"{level}环: {current}/{max_value}")
        return " | ".join(parts) if parts else None
