"""
状态分层摘要 - 为人类和LLM提供可读的状态视图
"""
from typing import Any


class StateSummarizer:
    """状态摘要生成器"""
    
    # 实体类型配置：定义哪些字段需要展示
    ENTITY_CONFIG = {
        "players": {
            "name": "名称",
            "combat": {
                "current_hp": "HP",
                "max_hp": "最大HP", 
                "armor_class": "AC",
                "proficiency_bonus": "熟练加值"
            },
            "attributes": {
                "strength": "力量",
                "dexterity": "敏捷",
                "constitution": "体质",
                "intelligence": "智力",
                "wisdom": "感知",
                "charisma": "魅力",
                "modifiers": {
                    "strength": "力量调整",
                    "dexterity": "敏捷调整",
                    "constitution": "体质调整",
                }
            },
            "equipment": {
                "weapons": {
                    "main_hand": {
                        "name": "主手武器",
                        "damage": "伤害骰"
                    }
                }
            }
        },
        "enemies": {
            "name": "名称",
            "current_hp": "HP",
            "max_hp": "最大HP",
            "ac": "AC",
            "attributes": {
                "strength": "力量",
                "dexterity": "敏捷",
            }
        },
        "objects": {
            "name": "名称",
            "state": "状态",
            "damage": {
                "fire_damage": "火焰伤害",
                "blast_radius": "爆炸范围"
            }
        }
    }
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
    
    def summarize_all(self, max_entities_per_type: int = 3) -> str:
        """
        生成完整的状态摘要
        
        示例输出：
        🧙 艾尔德拉·银誓 (玩家)
          战斗: HP 44/44 | AC 18 | 熟练+3
          属性: 力量16(+3) 敏捷12(+1) 体质14(+2) 智力10(0) 感知13(+1) 魅力18(+4)
          装备: 长剑+1(1d8+4) | 盾牌 | 链甲
        
        👹 地精掠夺者 (敌人)
          战斗: HP 7/7 | AC 15
          装备: 弯刀(1d6+2) | 短弓
        
        🛢️ 火药桶 (物品)
          状态: unlit | 爆炸范围10尺 | 火焰伤害4d6
        """
        lines = []
        state = self.state_manager.snapshot()
        
        # 遍历实体类型
        for entity_type in ["players", "enemies", "objects"]:
            entities = state.get("entity", {}).get(entity_type, {})
            
            for idx, (entity_id, entity_data) in enumerate(entities.items()):
                if idx >= max_entities_per_type:
                    break
                    
                summary = self._summarize_entity(entity_type, entity_id, entity_data)
                lines.append(summary)
                lines.append("")  # 空行分隔
        
        return "\n".join(lines)
    
    def summarize_entity(self, entity_path: str) -> str:
        """
        生成特定实体的详细摘要
        
        Args:
            entity_path: 如 "entity.players.player_01" 或 "艾尔德拉"
        """
        # 尝试通过名称查找
        state = self.state_manager.snapshot()
        
        # 先尝试直接路径
        if entity_path.startswith("entity."):
            try:
                entity_data = self.state_manager.get(entity_path)
                parts = entity_path.split(".")
                entity_type = parts[1]  # players/enemies/objects
                entity_id = parts[2]
                return self._summarize_entity(entity_type, entity_id, entity_data)
            except:
                pass
        
        # 通过名称查找
        for entity_type in ["players", "enemies", "objects"]:
            entities = state.get("entity", {}).get(entity_type, {})
            for entity_id, entity_data in entities.items():
                name = entity_data.get("name", "")
                if entity_path in name or name in entity_path:
                    return self._summarize_entity(entity_type, entity_id, entity_data)
        
        return f"未找到实体: {entity_path}"
    
    def _summarize_entity(self, entity_type: str, entity_id: str, data: dict) -> str:
        """生成单个实体的摘要"""
        name = data.get("name", entity_id)
        type_emoji = {"players": "🧙", "enemies": "👹", "objects": "🛢️"}.get(entity_type, "📦")
        type_name = {"players": "玩家", "enemies": "敌人", "objects": "物品"}.get(entity_type, "其他")
        
        lines = [f"{type_emoji} {name} ({type_name}, ID: {entity_id})"]
        
        # 战斗信息
        combat_info = self._extract_combat_info(entity_type, data)
        if combat_info:
            lines.append(f"  战斗: {' | '.join(combat_info)}")
        
        # 属性信息
        attr_info = self._extract_attributes_info(data)
        if attr_info:
            lines.append(f"  属性: {attr_info}")
        
        # 装备信息
        equip_info = self._extract_equipment_info(entity_type, data)
        if equip_info:
            lines.append(f"  装备: {equip_info}")
        
        # 特殊状态
        special_info = self._extract_special_info(entity_type, data)
        if special_info:
            lines.append(f"  特殊: {special_info}")
        
        return "\n".join(lines)
    
    def _extract_combat_info(self, entity_type: str, data: dict) -> list[str]:
        """提取战斗相关信息"""
        info = []
        
        if entity_type == "players":
            combat = data.get("combat", {})
            hp = combat.get("current_hp", "?")
            max_hp = combat.get("max_hp", "?")
            ac = combat.get("armor_class", "?")
            prof = combat.get("proficiency_bonus", "?")
            info.append(f"HP {hp}/{max_hp}")
            info.append(f"AC {ac}")
            info.append(f"熟练+{prof}")
        elif entity_type == "enemies":
            hp = data.get("current_hp", "?")
            max_hp = data.get("max_hp", "?")
            ac = data.get("ac", "?")
            info.append(f"HP {hp}/{max_hp}")
            info.append(f"AC {ac}")
        elif entity_type == "objects":
            state = data.get("state", "?")
            info.append(f"状态:{state}")
            damage = data.get("damage", {})
            if "fire_damage" in damage:
                info.append(f"火焰伤害{damage['fire_damage']}")
            if "blast_radius" in damage:
                info.append(f"爆炸范围{damage['blast_radius']}尺")
        
        return info
    
    def _extract_attributes_info(self, data: dict) -> str:
        """提取属性信息，格式: 力量16(+3) 敏捷12(+1) ..."""
        attrs = data.get("attributes", {})
        modifiers = attrs.get("modifiers", {})
        
        attr_names = {
            "strength": "力量",
            "dexterity": "敏捷", 
            "constitution": "体质",
            "intelligence": "智力",
            "wisdom": "感知",
            "charisma": "魅力"
        }
        
        parts = []
        for key, name in attr_names.items():
            if key in attrs:
                value = attrs[key]
                mod = modifiers.get(key, 0)
                mod_str = f"({mod:+d})" if mod != 0 else "(0)"
                parts.append(f"{name}{value}{mod_str}")
        
        return " ".join(parts) if parts else ""
    
    def _extract_equipment_info(self, entity_type: str, data: dict) -> str:
        """提取装备信息"""
        if entity_type == "players":
            equipment = data.get("equipment", {})
            weapons = equipment.get("weapons", {})
            main_hand = weapons.get("main_hand", {})
            
            parts = []
            if main_hand:
                weapon_name = main_hand.get("name", "未知武器")
                damage = main_hand.get("damage", "")
                parts.append(f"{weapon_name}({damage})")
            
            off_hand = weapons.get("off_hand", {})
            if off_hand:
                parts.append(off_hand.get("name", "副手"))
            
            armor = equipment.get("armor", {}).get("worn", {})
            if armor:
                parts.append(armor.get("name", "护甲"))
            
            return " | ".join(parts) if parts else ""
            
        elif entity_type == "enemies":
            combat = data.get("combat", {})
            weapons = combat.get("weapons", [])
            if weapons:
                return " | ".join([w.get("name", "武器") for w in weapons[:2]])
        
        return ""
    
    def _extract_special_info(self, entity_type: str, data: dict) -> str:
        """提取特殊信息"""
        info = []
        
        # 法术位
        if entity_type == "players":
            spell_slots = data.get("spell_slots", {})
            if spell_slots:
                slots = []
                for level, slot_data in spell_slots.items():
                    if isinstance(slot_data, dict):
                        current = slot_data.get("current", 0)
                        max_slots = slot_data.get("max", 0)
                        if max_slots > 0:
                            level_num = level.replace("level_", "")
                            slots.append(f"{level_num}环:{current}/{max_slots}")
                if slots:
                    info.append("法术位 " + " ".join(slots))
            
            # 已准备法术
            spells = data.get("spells", {}).get("prepared", {})
            if spells:
                cantrips = spells.get("cantrips", [])
                if cantrips:
                    info.append(f"戏法: {', '.join(cantrips[:3])}")
        
        return " | ".join(info) if info else ""


# 便捷函数
def format_state_for_llm(state_manager, focus_entities: list[str] = None) -> str:
    """
    为LLM格式化的状态摘要
    
    Args:
        state_manager: 状态管理器
        focus_entities: 需要重点展示的实体名称列表，如 ["艾尔德拉", "地精掠夺者"]
    """
    summarizer = StateSummarizer(state_manager)
    
    if focus_entities:
        # 只展示关注的实体
        summaries = []
        for entity_name in focus_entities:
            summary = summarizer.summarize_entity(entity_name)
            summaries.append(summary)
        return "\n\n".join(summaries)
    else:
        # 展示所有
        return summarizer.summarize_all()
