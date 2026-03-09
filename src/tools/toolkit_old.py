"""
TrpgToolkit - 组合 Logic、RAG、State 的 LangChain 工具箱
"""

from typing import Any, Literal, ClassVar
from difflib import get_close_matches

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import BaseModel, Field

from .logic import LogicEngine
from .rag import Retriever
from .state import StateManager


# ============================================
# 工具输入 Schema
# ============================================


class SearchInput(BaseModel):
    """RAG 检索工具输入"""
    query: str = Field(description="搜索查询文本")
    limit: int = Field(default=3, description="返回结果数量")


class EvaluateMechanicsInput(BaseModel):
    """表达式求值工具输入"""
    expression: str = Field(description="要执行的表达式，支持掷骰函数 Roll('XdY') 和点分隔状态路径引用，支持比较操作符如 >, < ,==, >=, <=, !=")


class FetchSchemaInput(BaseModel):
    """获取状态 schema 工具输入（无参数）"""
    pass


class PatchOperation(BaseModel):
    """单个修补操作"""
    op: Literal["set", "delete", "add", "subtract", "multiply", "divide", "append"] = Field(
        description="操作类型: set(设置), delete(删除), add(数值加), subtract(数值减), multiply(数值乘), divide(数值除), append(列表追加)"
    )
    path: str = Field(description="目标路径，点分隔符表示层级，如 entities.warrior.hp")
    value: Any | None = Field(
        default=None,
        description="操作值。set/add/subtract/multiply/divide/append 需要。delete 不需要"
    )


class BatchPatchInput(BaseModel):
    """批量修补状态工具输入"""
    patches: list[PatchOperation] = Field(description="修补操作列表，按顺序执行")


class BatchGetInput(BaseModel):
    """批量获取状态工具输入"""
    paths: list[str] = Field(description="要获取的路径列表")


class FetchKeysInput(BaseModel):
    """路径检索工具输入"""
    keys: str = Field(description="查询关键词，如'艾尔德拉 hp'、'goblin ac'。支持多个关键词用空格分隔")
    top_k: int = Field(default=3, description="返回最匹配的候选路径数量")


# ============================================
# 工具实现
# ============================================

class SearchTool(BaseTool):
    """RAG 检索工具"""
    name: str = "search"
    description: str = "搜索 D&D 5e SRD 规则文档，返回相关规则说明"
    args_schema: type[BaseModel] = SearchInput

    retriever: Retriever = Field(exclude=True)

    def _run(self, query: str, limit: int = 3) -> str:
        results = self.retriever.search(query, limit=limit)
        if not results:
            return "未找到相关结果"

        output_lines = []
        for i, result in enumerate(results, 1):
            score = result.get("score", 0)
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            title = metadata.get("title", "无标题")
            file = metadata.get("file", "未知")

            output_lines.append(f"[{i}] {title} (来源: {file}, 相关性: {score:.2f})")
            output_lines.append(content)

            parent = result.get("parent_content")
            if parent:
                output_lines.append(f"上下文: {parent}")

            output_lines.append("")

        return "\n".join(output_lines)


class EvaluateMechanicsTool(BaseTool):
    """表达式求值工具（掷骰+状态引用）"""
    name: str = "evaluate_mechanics"
    description: str = "执行游戏机制表达式，支持掷骰 Roll('XdY') 和状态路径引用（如 entities.warrior.hp）"
    args_schema: type[BaseModel] = EvaluateMechanicsInput

    logic_engine: LogicEngine = Field(exclude=True)
    state_manager: StateManager = Field(exclude=True)

    def _run(self, expression: str) -> str:
        state = self.state_manager.snapshot()
        result = self.logic_engine.eval(expression, state)
        return f"结果: {result.result}\n轨迹: {result.resolved}"


class FetchSchemaTool(BaseTool):
    """获取状态 schema 工具"""
    name: str = "fetch_schema"
    description: str = "获取当前世界状态的类型结构 schema"
    args_schema: type[BaseModel] = FetchSchemaInput

    state_manager: StateManager = Field(exclude=True)

    def _run(self) -> str:
        import json
        schema = self.state_manager.get_schema()
        return json.dumps(schema, ensure_ascii=False, indent=2)


class BatchPatchTool(BaseTool):
    """批量修补状态工具，支持增删改和数值操作"""
    name: str = "modify_state"
    description: str = (
        "批量修改世界状态。支持操作: "
        "set(设置值), delete(删除), add(数值加), subtract(数值减), "
        "multiply(数值乘), divide(数值除), append(向列表追加元素)"
    )
    args_schema: type[BaseModel] = BatchPatchInput

    state_manager: StateManager = Field(exclude=True)

    def _run(self, patches: list[PatchOperation]) -> str:
        results = []
        for patch in patches:
            op, path, value = patch.op, patch.path, patch.value
            try:
                if op == "set":
                    if value is None:
                        results.append(f"❌ set 操作需要 value: {path}")
                        continue
                    self.state_manager.set(path, value)
                    results.append(f"✓ set {path} = {value}")

                elif op == "delete":
                    deleted = self.state_manager.delete(path)
                    results.append(f"✓ delete {path} (原值: {deleted})")

                elif op == "add":
                    if value is None:
                        results.append(f"❌ add 操作需要 value: {path}")
                        continue
                    new_val = self.state_manager.add(path, value)
                    results.append(f"✓ add {path} += {value} → {new_val}")

                elif op == "subtract":
                    if value is None:
                        results.append(f"❌ subtract 操作需要 value: {path}")
                        continue
                    new_val = self.state_manager.subtract(path, value)
                    results.append(f"✓ subtract {path} -= {value} → {new_val}")

                elif op == "multiply":
                    if value is None:
                        results.append(f"❌ multiply 操作需要 value: {path}")
                        continue
                    new_val = self.state_manager.multiply(path, value)
                    results.append(f"✓ multiply {path} *= {value} → {new_val}")

                elif op == "divide":
                    if value is None:
                        results.append(f"❌ divide 操作需要 value: {path}")
                        continue
                    new_val = self.state_manager.divide(path, value)
                    results.append(f"✓ divide {path} /= {value} → {new_val}")

                elif op == "append":
                    if value is None:
                        results.append(f"❌ append 操作需要 value: {path}")
                        continue
                    # 获取当前列表并追加
                    current = self.state_manager.get(path)
                    if not isinstance(current, list):
                        results.append(f"❌ append 目标不是列表: {path}")
                        continue
                    current.append(value)
                    results.append(f"✓ append to {path}: {value}")

                else:
                    results.append(f"❌ 未知操作: {op}")

            except Exception as e:
                results.append(f"❌ {op} {path} 失败: {e}")

        return "\n".join(results)


class BatchGetTool(BaseTool):
    """批量获取状态工具"""
    name: str = "batch_get"
    description: str = "批量获取指定路径的状态值"
    args_schema: type[BaseModel] = BatchGetInput

    state_manager: StateManager = Field(exclude=True)

    def _run(self, paths: list[str]) -> str:
        import json
        result = {}
        for path in paths:
            try:
                result[path] = self.state_manager.get(path)
            except KeyError:
                result[path] = None
        return json.dumps(result, ensure_ascii=False)


class FetchKeysTool(BaseTool):
    """
    路径检索工具 - 根据查询关键词返回候选的属性路径。
    
    接收类似"艾尔德拉 hp"的关键词，返回最匹配的候选路径（默认3个）。
    主LLM应该根据返回的路径列表，选择最合适的路径来使用。
    """
    name: str = "fetchkeys"
    description: str = (
        "根据查询关键词检索候选的状态路径。"
        "输入如'艾尔德拉 hp'、'goblin ac'等关键词，返回最匹配的属性路径列表。"
        "你应该根据返回的候选路径，选择最合适的路径用于batch_get或modify_state。"
    )
    args_schema: type[BaseModel] = FetchKeysInput

    state_manager: StateManager = Field(exclude=True)

    def _run(self, keys: str, top_k: int = 3) -> str:
        import json
        
        keywords = keys.lower().strip().split()
        all_paths = self._collect_candidate_paths()
        
        # 1. 先识别相关实体（通过名称匹配）
        matched_entities = self._match_entities_by_name(keywords)
        entity_prefixes = [e["path_prefix"] for e in matched_entities]
        
        # 2. 计算每个路径的匹配分数（结合实体前缀）
        scored_paths = []
        for path in all_paths:
            score = self._calculate_match_score(path, keywords, entity_prefixes)
            if score > 0:
                scored_paths.append((path, score))
        
        # 按分数排序，取 top_k
        scored_paths.sort(key=lambda x: x[1], reverse=True)
        top_matches = scored_paths[:top_k]
        
        # 构建返回结果
        results = []
        for path, score in top_matches:
            try:
                value = self.state_manager.get(path)
                value_preview = str(value)[:80] + "..." if len(str(value)) > 80 else str(value)
                results.append({
                    "path": path,
                    "score": round(score, 2),
                    "value_preview": value_preview
                })
            except KeyError:
                results.append({
                    "path": path,
                    "score": round(score, 2),
                    "value_preview": "[无法访问]"
                })
        
        # 返回包含schema提示的结果
        return json.dumps({
            "query_keys": keywords,
            "candidates": results,
            "matched_entities": matched_entities
        }, ensure_ascii=False, indent=2)
    
    def _collect_candidate_paths(self) -> list[str]:
        """收集所有候选路径（叶子节点）"""
        return [path for path, _ in self.state_manager.get_all_leaf_paths()]
    
    def _match_entities_by_name(self, keywords: list[str]) -> list[dict]:
        """
        根据关键词匹配实体名称，返回匹配的实体信息。
        例如 "艾尔德拉" 会匹配到 name="艾尔德拉·银誓" 的 player_01
        """
        state = self.state_manager.snapshot()
        matched = []
        
        for category in ["players", "enemies", "objects"]:
            entities = state.get("entity", {}).get(category, {})
            for eid, edata in entities.items():
                name = edata.get("name", "")
                name_lower = name.lower()
                
                # 检查是否匹配任何关键词
                for kw in keywords:
                    # 完全匹配、包含匹配或简称匹配
                    if (kw == name_lower or 
                        kw in name_lower or 
                        name_lower.startswith(kw)):
                        matched.append({
                            "name": name,
                            "id": eid,
                            "category": category,
                            "path_prefix": f"entity.{category}.{eid}",
                            "matched_keyword": kw
                        })
                        break
        
        return matched
    
    # 常见属性别名映射
    ATTR_ALIASES: ClassVar[dict] = {
        "hp": ["current_hp", "max_hp", "temp_hp", "hit_dice"],
        "生命值": ["current_hp", "max_hp"],
        "生命": ["current_hp", "max_hp"],
        "ac": ["armor_class", "ac"],
        "护甲": ["armor_class"],
        "护甲值": ["armor_class"],
        "str": ["strength"],
        "力量": ["strength"],
        "dex": ["dexterity"],
        "敏捷": ["dexterity"],
        "con": ["constitution"],
        "体质": ["constitution"],
        "int": ["intelligence"],
        "智力": ["intelligence"],
        "wis": ["wisdom"],
        "感知": ["wisdom"],
        "cha": ["charisma"],
        "魅力": ["charisma"],
    }

    def _calculate_match_score(self, path: str, keywords: list[str], entity_prefixes: list[str]) -> float:
        """计算路径与关键词的匹配分数"""
        path_lower = path.lower()
        score = 0.0
        
        # 1. 如果路径属于已识别的实体，给予基础加分
        matched_entity = None
        for prefix in entity_prefixes:
            if path_lower.startswith(prefix.lower()):
                score += 2.0  # 实体匹配的基础分
                matched_entity = prefix
                break
        
        # 2. 关键词匹配（属性部分）
        for kw in keywords:
            kw_lower = kw.lower()
            
            # 跳过已用于实体匹配的关键词
            if matched_entity and any(kw_lower in e.lower() for e in entity_prefixes):
                continue
            
            # 检查是否是属性别名
            if kw_lower in self.ATTR_ALIASES:
                # 别名匹配到实际路径
                for actual_attr in self.ATTR_ALIASES[kw_lower]:
                    if actual_attr in path_lower:
                        score += 1.5  # 别名匹配加分
                        if path_lower.endswith(actual_attr):
                            score += 0.5
                        break
            
            # 完整匹配路径的一部分（ID或属性）
            elif kw_lower in path_lower:
                score += 1.0
                # 如果是路径的最后一部分（属性名），额外加分
                if path_lower.endswith(kw_lower):
                    score += 0.5
        
        return score
    






# ============================================
# 工具箱
# ============================================

class TrpgToolkit(BaseToolkit):
    """TRPG 工具箱，组合 Logic、RAG、State 三个核心类"""

    def __init__(self, initial_state: dict[str, Any] | None = None, **kwargs):
        self._state_manager = StateManager(initial_state)
        self._logic_engine = LogicEngine()
        self._retriever = Retriever(**kwargs)

    @property
    def state_manager(self) -> StateManager:
        return self._state_manager

    @property
    def logic_engine(self) -> LogicEngine:
        return self._logic_engine

    @property
    def retriever(self) -> Retriever:
        return self._retriever

    def get_tools(self) -> list[BaseTool]:
        """返回所有工具"""
        return [
            SearchTool(retriever=self._retriever),
            EvaluateMechanicsTool(
                logic_engine=self._logic_engine,
                state_manager=self._state_manager
            ),
            FetchSchemaTool(state_manager=self._state_manager),
            BatchPatchTool(state_manager=self._state_manager),
            BatchGetTool(state_manager=self._state_manager),
            FetchKeysTool(state_manager=self._state_manager),
        ]