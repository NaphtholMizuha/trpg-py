"""
StateSummarizer - 使用LLM将状态Schema转换为人类可读摘要
支持按实体缓存摘要，避免重复调用LLM
"""
import json
import hashlib
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from ..core.task_intent import TaskIntent
from ..core.paths import RelevantPaths


class LLMStateSummarizer:
    """使用LLM生成状态摘要，支持缓存"""
    
    def __init__(self, model: str = "deepseek-chat", api_key: str | None = None, base_url: str | None = None, cache_dir: str = ".cache/summaries"):
        self.use_llm = api_key is not None
        if self.use_llm:
            kwargs = {"model": model, "temperature": 0.3, "api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.llm = ChatOpenAI(**kwargs)
        else:
            self.llm = None
        self.state_manager = None
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache = {}  # 内存缓存
    
    def set_state_manager(self, state_manager):
        """设置状态管理器"""
        self.state_manager = state_manager
    
    def _get_structure_hash(self, entity_data: dict) -> str:
        """
        计算实体结构的哈希值（不包含具体数值）
        这样数值变化时不会重新生成摘要
        """
        # 只提取字段结构（键和值的类型），忽略具体数值
        def extract_structure(obj):
            if isinstance(obj, dict):
                return {k: extract_structure(v) for k, v in sorted(obj.items())}
            elif isinstance(obj, list):
                # 对于数组，只记录长度和元素类型（如果是对象）
                if obj and isinstance(obj[0], dict):
                    return [extract_structure(obj[0])] if obj else []
                return []
            else:
                # 叶子节点只返回类型，不返回值
                return type(obj).__name__
        
        structure = extract_structure(entity_data)
        data_str = json.dumps(structure, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data_str.encode()).hexdigest()[:16]
    
    def _get_cache_path(self, entity_id: str, entity_hash: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{entity_id}_{entity_hash}.txt"
    
    def _load_from_cache(self, entity_id: str, entity_hash: str) -> str | None:
        """从缓存加载摘要"""
        cache_key = f"{entity_id}_{entity_hash}"
        
        # 先查内存缓存
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 再查文件缓存
        cache_path = self._get_cache_path(entity_id, entity_hash)
        if cache_path.exists():
            summary = cache_path.read_text(encoding="utf-8")
            self._cache[cache_key] = summary  # 放入内存缓存
            return summary
        
        return None
    
    def _save_to_cache(self, entity_id: str, entity_hash: str, summary: str):
        """保存摘要到缓存"""
        cache_key = f"{entity_id}_{entity_hash}"
        self._cache[cache_key] = summary  # 内存缓存
        
        # 文件缓存
        cache_path = self._get_cache_path(entity_id, entity_hash)
        cache_path.write_text(summary, encoding="utf-8")
    
    def summarize(self, task_description: str, focus_entities: list[str] = None) -> str:
        """
        生成状态路径摘要（只包含叶子路径，不包含具体数值）
        优先从缓存读取，如果没有则调用LLM生成
        
        Args:
            task_description: 任务描述，帮助LLM判断哪些信息重要
            focus_entities: 关注的实体名称列表，如["艾尔德拉", "地精掠夺者"]
        """
        if not self.use_llm or not self.state_manager:
            return self._fallback_summarize(focus_entities)
        
        # 获取完整状态
        state = self.state_manager.snapshot()
        
        summaries = []
        need_llm_entities = []  # 需要调用LLM生成的实体
        
        # 确定要处理的实体
        entities_to_process = []
        for entity_type in ["players", "enemies", "objects"]:
            entities = state.get("entity", {}).get(entity_type, {})
            for entity_id, entity_data in entities.items():
                # 如果指定了关注实体，过滤
                if focus_entities:
                    name = entity_data.get("name", "")
                    match = any(n in name or name in n for n in focus_entities)
                    if not match:
                        continue
                
                entities_to_process.append((entity_type, entity_id, entity_data))
        
        # 尝试从缓存获取每个实体的摘要
        for entity_type, entity_id, entity_data in entities_to_process:
            entity_hash = self._get_structure_hash(entity_data)
            cached_summary = self._load_from_cache(entity_id, entity_hash)
            
            if cached_summary:
                print(f"   📋 从缓存加载 [{entity_id}] 摘要")
                summaries.append(cached_summary)
            else:
                need_llm_entities.append((entity_type, entity_id, entity_data))
        
        # 对需要LLM的实体生成摘要
        if need_llm_entities:
            llm_summaries = self._generate_llm_summaries(
                need_llm_entities, task_description
            )
            summaries.extend(llm_summaries)
        
        return "\n\n".join(summaries)
    
    def _generate_llm_summaries(self, entities: list, task_description: str) -> list[str]:
        """调用LLM生成实体摘要"""
        summaries = []
        
        for entity_type, entity_id, entity_data in entities:
            # 提取该实体的叶子路径
            leaf_paths = self._extract_entity_leaf_paths(entity_data, f"entity.{entity_type}.{entity_id}")
            
            summary = self._call_llm_for_summary(entity_id, entity_data, leaf_paths, task_description)
            
            if summary:
                # 保存到缓存（使用结构哈希，不包含数值）
                entity_hash = self._get_structure_hash(entity_data)
                self._save_to_cache(entity_id, entity_hash, summary)
                summaries.append(summary)
        
        return summaries
    
    def _extract_entity_leaf_paths(self, data: dict, prefix: str) -> list[str]:
        """提取单个实体的所有叶子路径"""
        paths = []
        
        def traverse(obj, path):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}"
                    if isinstance(value, (dict, list)):
                        traverse(value, new_path)
                    else:
                        paths.append(f"{new_path}: {type(value).__name__}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    new_path = f"{path}.{i}"
                    if isinstance(item, (dict, list)):
                        traverse(item, new_path)
                    else:
                        paths.append(f"{new_path}: {type(item).__name__}")
        
        traverse(data, prefix)
        return paths
    
    def _call_llm_for_summary(self, entity_id: str, entity_data: dict, leaf_paths: list[str], task_description: str) -> str | None:
        """调用LLM生成单个实体摘要"""
        entity_name = entity_data.get("name", entity_id)
        entity_type = self._guess_entity_type(entity_data)
        
        system_prompt = """你是一个TRPG实体状态摘要生成器。

你的任务是将实体字段路径列表转换为简洁的摘要。

输入：
- 实体名称和类型
- 该实体的所有可用字段路径（点分格式）
- 当前任务描述

重要规则：
1. 只能从提供的字段路径列表中选择，不能编造不存在的路径
2. 不要添加列表中没有的字段（如attack_bonus如果不存在就不要写）
3. 只列出与战斗相关的字段路径
4. 使用完整点分路径格式，数组使用 .0 .1 索引
5. 不要包含具体数值

格式示例：

🧙 {实体名称} ({类型}, ID: {ID})
- 生命值路径: entity.players.player_01.combat.current_hp
- AC路径: entity.players.player_01.combat.armor_class
- 力量调整值: entity.players.player_01.attributes.modifiers.strength
- 主手武器伤害: entity.players.player_01.equipment.weapons.main_hand.damage
- 武器魔法加值: entity.players.player_01.equipment.weapons.main_hand.magic_bonus
"""
        
        prompt = f"""实体名称: {entity_name}
实体ID: {entity_id}
实体类型: {entity_type}

当前任务: {task_description}

该实体的可用字段路径:
{chr(10).join(leaf_paths[:50])}  # 限制数量避免超出上下文

请生成该实体的状态摘要，列出关键战斗字段路径。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            summary = response.content.strip()
            
            # 清理markdown代码块
            if summary.startswith("```"):
                lines = summary.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                summary = "\n".join(lines).strip()
            
            return summary
            
        except Exception as e:
            print(f"   ⚠️ LLM摘要生成失败 [{entity_id}]: {e}")
            return None
    
    def _guess_entity_type(self, entity_data: dict) -> str:
        """猜测实体类型"""
        if "class" in entity_data:
            return "玩家"
        elif "cr" in entity_data or "xp_value" in entity_data:
            return "敌人"
        elif "state" in entity_data and "interact_options" in entity_data:
            return "物品"
        return "其他"
    
    def _fallback_summarize(self, focus_entities: list[str] = None) -> str:
        """Fallback：简单的关键信息提取"""
        if not self.state_manager:
            return "状态加载失败"
        
        state = self.state_manager.snapshot()
        lines = []
        
        for entity_type in ["players", "enemies", "objects"]:
            entities = state.get("entity", {}).get(entity_type, {})
            for entity_id, entity_data in entities.items():
                name = entity_data.get("name", entity_id)
                
                # 如果指定了关注实体，过滤
                if focus_entities:
                    match = any(n in name or name in n for n in focus_entities)
                    if not match:
                        continue
                
                emoji = {"players": "🧙", "enemies": "👹", "objects": "🛢️"}.get(entity_type, "📦")
                lines.append(f"{emoji} {name} (ID: {entity_id})")
                
                # 简单提取HP和AC
                if "combat" in entity_data:
                    combat = entity_data["combat"]
                    hp = combat.get("current_hp", "?")
                    max_hp = combat.get("max_hp", "?")
                    ac = combat.get("armor_class", "?")
                    lines.append(f"  HP: {hp}/{max_hp}, AC: {ac}")
        
        return "\n".join(lines) if lines else "无相关实体"
    
    def clear_cache(self):
        """清除所有缓存"""
        self._cache.clear()
        for f in self.cache_dir.glob("*.txt"):
            f.unlink()
        print("🗑️  摘要缓存已清除")
