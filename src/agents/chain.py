"""
ChainAgent - 连锁Agent，检测状态变更触发的连锁反应
"""
from ..types import StateChange
from ..types import ChainTrigger


class ChainAgent:
    """连锁Agent - 检测状态变更触发的连锁反应"""
    
    def check_chains(self, changes: list[StateChange], world_state: dict) -> list[ChainTrigger]:
        """检查是否有连锁反应"""
        triggers = []
        
        for change in changes:
            if "current_hp" in change.path and isinstance(change.new_value, (int, float)) and change.new_value <= 0:
                path_parts = change.path.split(".")
                if len(path_parts) >= 3:
                    entity_type = path_parts[1]
                    entity_id = path_parts[2]
                    
                    entity_data = world_state.get("entity", {}).get(entity_type, {}).get(entity_id, {})
                    entity_name = entity_data.get("name", entity_id)
                    
                    triggers.append(ChainTrigger(
                        condition=f"{entity_name} HP ≤ 0",
                        effect=f"{entity_name} 死亡，触发死亡连锁",
                        priority=1
                    ))
            
            if "explosive_barrel.state" in change.path and change.new_value == "lit":
                triggers.append(ChainTrigger(
                    condition="火药桶被点燃",
                    effect="6秒后爆炸，范围内所有生物受到 4d6 火焰 + 2d6 钝击伤害",
                    priority=2
                ))
        
        return triggers
