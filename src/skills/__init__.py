"""
Skills Registry - Anthropic风格的Skill系统

用于意图识别和动态加载skill指令
"""
from pathlib import Path
from dataclasses import dataclass, field
import yaml
from typing import Optional


@dataclass
class Skill:
    """Skill定义"""
    name: str
    description: str
    content: str
    trigger_keywords: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class SkillRegistry:
    """Skill注册表 - 加载和管理skills"""

    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or Path(__file__).parent.parent.parent / "skills"
        self._skills: dict[str, Skill] = {}
        self._load_all_skills()

    def _load_all_skills(self):
        """加载所有skill"""
        if not self.skills_dir.exists():
            return

        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    skill = self._parse_skill(skill_file)
                    if skill:
                        self._skills[skill.name] = skill

    def _parse_skill(self, filepath: Path) -> Optional[Skill]:
        """解析SKILL.md文件"""
        content = filepath.read_text(encoding="utf-8")

        # 解析YAML frontmatter
        if not content.startswith("---"):
            return None

        end_idx = content.find("---", 3)
        if end_idx == -1:
            return None

        yaml_content = content[3:end_idx].strip()
        md_content = content[end_idx + 3:].strip()

        try:
            metadata = yaml.safe_load(yaml_content)
        except yaml.YAMLError:
            return None

        metadata = metadata or {}
        extra_metadata = metadata.get("metadata", {}) or {}
        trigger_keywords = metadata.get("trigger_keywords", extra_metadata.get("trigger_keywords", []))

        return Skill(
            name=metadata.get("name", filepath.parent.name),
            description=metadata.get("description", ""),
            trigger_keywords=trigger_keywords,
            content=md_content,
            metadata=extra_metadata,
        )

    def get_skill(self, name: str) -> Optional[Skill]:
        """获取指定名称的skill"""
        return self._skills.get(name)

    def get_combat_skill(self) -> Optional[Skill]:
        """获取combat skill"""
        return self._skills.get("combat")

    def get_world_edit_skill(self) -> Optional[Skill]:
        """获取world_edit skill"""
        return self._skills.get("world_edit") or self._skills.get("trpg-world-edit")

    def list_skills(self) -> list[str]:
        """列出所有skill名称"""
        return list(self._skills.keys())

    def get_all_skills(self) -> dict[str, Skill]:
        """获取所有skills"""
        return self._skills.copy()


# 全局注册表实例
_skill_registry: Optional[SkillRegistry] = None


def get_registry() -> SkillRegistry:
    """获取全局skill注册表"""
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()
    return _skill_registry


def detect_intent_with_keywords(user_input: str) -> tuple[str, Optional[Skill]]:
    """
    使用关键词匹配检测意图（备用方法）

    Returns:
        (intent_type, skill)
        intent_type: "standard" | "world_edit"
    """
    user_lower = user_input.lower()
    registry = get_registry()

    # world_edit优先
    world_edit = registry.get_world_edit_skill()
    if world_edit:
        for keyword in world_edit.trigger_keywords:
            if keyword.lower() in user_lower:
                return "world_edit", world_edit

    # 然后combat
    combat = registry.get_combat_skill()
    if combat:
        for keyword in combat.trigger_keywords:
            if keyword.lower() in user_lower:
                return "standard", combat

    # 默认combat
    return "standard", combat

# 导出
__all__ = [
    "Skill",
    "SkillRegistry",
    "get_registry",
    "detect_intent_with_keywords",
]
