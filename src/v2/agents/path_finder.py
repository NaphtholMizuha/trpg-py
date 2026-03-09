"""
PathFinder - 路径检索Agent，使用LLM根据任务和全局状态检索相关路径
"""
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from ..core.task_intent import TaskIntent
from ..core.paths import RelevantPaths


class PathFinder:
    """路径检索Agent - 使用LLM根据全局状态动态检索相关路径"""
    
    def __init__(self, model: str = "deepseek-chat", api_key: str | None = None, base_url: str | None = None):
        self.use_llm = api_key is not None
        if self.use_llm:
            kwargs = {"model": model, "temperature": 0, "api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.llm = ChatOpenAI(**kwargs)
        else:
            self.llm = None
        self.state_manager = None
    
    def set_state_manager(self, state_manager):
        """设置状态管理器，用于获取全局状态schema"""
        self.state_manager = state_manager
    
    def find_paths(self, task: TaskIntent) -> RelevantPaths:
        """根据任务和全局状态找到相关路径"""
        if not self.use_llm or not self.state_manager:
            return self._fallback_paths(task)
        
        # 获取全局状态的schema（结构，不含值）
        schema = self._get_state_schema()
        
        system_prompt = """你是一个D&D 5e战斗系统的路径检索专家。

你的任务是根据任务描述和全局状态结构，找出执行任务所需的相关状态路径。

输入包含：
1. 全局状态的schema（只有结构，没有具体值）
2. 当前任务描述（行动者、目标、动作类型）

输出必须是JSON格式：
{
    "primary_paths": {
        "entity.players.player_01.attributes.strength": "int",
        "entity.enemies.goblin_01.ac": "int",
        ...
    },
    "reasoning": "选择这些路径的原因"
}

选择路径的原则：
1. 攻击任务需要：攻击者的属性（力量、调整值、熟练加值）、武器伤害，目标的AC和HP
2. 法术任务需要：施法者的施法属性、法术DC、法术位，目标的HP和豁免相关属性
3. 环境互动需要：互动对象的状态字段
4. 只选择必要的路径，不要返回无关字段
5. 路径必须存在于提供的schema中

只输出JSON，不要其他解释。"""

        prompt = f"""全局状态Schema：
```json
{json.dumps(schema, ensure_ascii=False, indent=2)}
```

当前任务：
- 描述：{task.description}
- 行动者：{task.actor}
- 目标：{task.target}
- 动作：{task.action}
- 类型：{task.task_type.value}

请返回相关路径。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            content = response.content.strip()
            
            # 清理 markdown 代码块标记
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            
            primary_paths = data.get("primary_paths", {})
            
            # 验证路径是否存在于schema中
            valid_paths = self._validate_paths(primary_paths, schema)
            
            print(f"   🤖 LLM选择路径 ({len(valid_paths)}):")
            for p, t in list(valid_paths.items())[:5]:
                print(f"     - {p}: {t}")
            if len(valid_paths) > 5:
                print(f"     ... 还有 {len(valid_paths) - 5} 条")
            
            return RelevantPaths(
                primary_paths=valid_paths,
                related_paths={}
            )
            
        except Exception as e:
            print(f"   ⚠️ LLM路径检索失败: {e}，使用fallback")
            return self._fallback_paths(task)
    
    def _get_state_schema(self) -> dict:
        """获取状态的结构schema（不含值）"""
        state = self.state_manager.snapshot()
        return self._extract_schema(state)
    
    def _extract_schema(self, obj, max_depth: int = 4, current_depth: int = 0) -> dict | str:
        """从状态中提取结构schema"""
        if current_depth >= max_depth:
            return "..."
        
        if isinstance(obj, dict):
            return {
                k: self._extract_schema(v, max_depth, current_depth + 1)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            if obj:
                return [self._extract_schema(obj[0], max_depth, current_depth + 1)]
            return []
        else:
            return type(obj).__name__
    
    def _validate_paths(self, paths: dict, schema: dict) -> dict:
        """验证路径是否存在于schema中"""
        valid = {}
        for path, path_type in paths.items():
            if self._path_exists_in_schema(path, schema):
                valid[path] = path_type
        return valid
    
    def _path_exists_in_schema(self, path: str, schema: dict) -> bool:
        """检查路径是否存在于schema中"""
        parts = path.split(".")
        current = schema
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False
        
        return True
    
    def _fallback_paths(self, task: TaskIntent) -> RelevantPaths:
        """回退：使用硬编码规则"""
        primary_paths = {}
        
        # 简化的硬编码映射
        ENTITY_MAP = {
            "艾尔德拉": "entity.players.player_01",
            "地精掠夺者": "entity.enemies.goblin_01",
            "火药桶": "entity.objects.explosive_barrel",
        }
        
        actor_base = ENTITY_MAP.get(task.actor)
        if actor_base and task.task_type.value == "attack":
            primary_paths[f"{actor_base}.attributes.modifiers.strength"] = "int"
        
        target_base = ENTITY_MAP.get(task.target) if task.target else None
        if target_base:
            if "goblin" in target_base:
                primary_paths[f"{target_base}.ac"] = "int"
                primary_paths[f"{target_base}.current_hp"] = "int"
            elif "barrel" in target_base:
                primary_paths[f"{target_base}.state"] = "str"
        
        return RelevantPaths(
            primary_paths=primary_paths,
            related_paths={}
        )
