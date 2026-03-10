"""
TrpgToolkit - 极简工具箱
仅包含 4 个核心工具:
- SearchTool: RAG 检索
- EvaluateTool: 执行 Roll() 表达式
- GetStateTool: 获取完整状态文本
- PatchStateTool: ADD/MOD/DEL 操作
"""

from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool, BaseToolkit

from .logic import LogicEngine
from .rag import Retriever
from .kv_state import KVStateStore


# ============================================
# 工具输入 Schema
# ============================================

class SearchInput(BaseModel):
    """RAG 检索工具输入"""
    query: str = Field(description="搜索查询文本")
    limit: int = Field(default=3, description="返回结果数量")


class EvaluateInput(BaseModel):
    """表达式求值工具输入"""
    expression: str = Field(
        description="要执行的表达式，支持掷骰函数 Roll('XdY') 和数值运算。"
                    "示例: \"Roll('1d20') + 3 >= 15\", \"Roll('2d6') + 4\", \"Roll('2d6') if Roll('1d20') >= 15 else 0\""
    )


class GetStateInput(BaseModel):
    """获取状态工具输入（无参数）"""
    pass


class PatchOperation(BaseModel):
    """单个修补操作"""
    op: str = Field(
        description="操作类型: ADD(添加), MOD(修改), DEL(删除)"
    )
    key: str = Field(
        description="目标 key，如 'Aldera.combat', 'Goblin.status'"
    )
    value: str = Field(
        default="",
        description="操作值（ADD/MOD 需要完整的自然语言段落，DEL 不需要）"
    )


class PatchStateInput(BaseModel):
    """修补状态工具输入"""
    operations: list[dict] = Field(
        description="操作列表，每个操作包含 op, key, value(可选)。"
                    "示例: [{\"op\": \"MOD\", \"key\": \"Aldera.combat\", \"value\": \"HP: 38/44 | AC: 18...\"}]"
    )


class ReadInput(BaseModel):
    """读取状态工具输入"""
    keys: list[str] = Field(description="要读取的状态键列表，如 ['Aldera.combat', 'Goblin.status']")


class FetchKeysInput(BaseModel):
    """获取所有key列表工具输入"""
    pass


class WriteInput(BaseModel):
    """写入状态工具输入（PatchState的简化版）"""
    operations: list[dict] = Field(
        description="操作列表，支持 ADD(添加), MOD(修改), DEL(删除)。"
                    "示例: [{\"op\": \"MOD\", \"key\": \"Aldera.combat\", \"value\": \"HP: 38/44...\"}]"
    )


# ============================================
# 工具实现
# ============================================

class SearchTool(BaseTool):
    """RAG 检索工具 - 搜索 D&D 5e SRD 规则文档"""
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


class EvaluateTool(BaseTool):
    """表达式求值工具 - 执行掷骰和数值运算"""
    name: str = "evaluate"
    description: str = (
        "执行游戏机制表达式，支持掷骰 Roll('XdY') 和数值运算。"
        "示例: Roll('1d20') + 3 >= 15, Roll('2d6') + 4"
    )
    args_schema: type[BaseModel] = EvaluateInput

    logic_engine: LogicEngine = Field(exclude=True)

    def _run(self, expression: str) -> str:
        try:
            result = self.logic_engine.eval(expression)
            return f"结果: {result.result}\n轨迹: {result.resolved}"
        except Exception as e:
            return f"执行错误: {e}"


class GetStateTool(BaseTool):
    """获取世界状态工具 - 返回完整 KV 文本"""
    name: str = "get_state"
    description: str = "获取完整的世界状态文本，包含所有角色和对象的当前状态"
    args_schema: type[BaseModel] = GetStateInput

    store: KVStateStore = Field(exclude=True)

    def _run(self) -> str:
        return self.store.get_text()


class PatchStateTool(BaseTool):
    """修补状态工具 - ADD/MOD/DEL 操作"""
    name: str = "patch_state"
    description: str = (
        "批量修改世界状态。支持 ADD(添加), MOD(修改), DEL(删除) 操作。"
        "value 必须是完整的自然语言段落，不是单个字段。"
    )
    args_schema: type[BaseModel] = PatchStateInput

    store: KVStateStore = Field(exclude=True)

    def _run(self, operations: list[dict]) -> str:
        success, changes = self.store.patch(operations)

        if not changes:
            return "未应用任何变更"

        lines = []
        for c in changes:
            if c.operation == "ADD":
                lines.append(f"✓ ADD [{c.key}] = {c.new_value[:50]}...")
            elif c.operation == "MOD":
                old_preview = (c.old_value[:30] + "...") if c.old_value else "None"
                lines.append(f"✓ MOD [{c.key}]: {old_preview} → {c.new_value[:50]}...")
            elif c.operation == "DEL":
                lines.append(f"✓ DEL [{c.key}] (原值: {c.old_value[:50]}...)")

        status = "成功" if success else "部分失败"
        return f"[{status}] 应用了 {len(changes)} 个变更:\n" + "\n".join(lines)


class ReadTool(BaseTool):
    """读取状态工具 - 读取指定key(s)的KV记忆value"""
    name: str = "read"
    description: str = "读取指定key(s)的KV记忆value，支持批量读取多个key"
    args_schema: type[BaseModel] = ReadInput

    store: KVStateStore = Field(exclude=True)

    def _run(self, keys: list[str]) -> str:
        results = []
        for key in keys:
            value = self.store.get(key)
            if value:
                results.append(f"[{key}] {value}")
            else:
                results.append(f"[{key}] 不存在")
        return "\n".join(results)


class FetchKeysTool(BaseTool):
    """获取所有key列表工具"""
    name: str = "fetch_keys"
    description: str = "获取所有KV记忆的key列表"
    args_schema: type[BaseModel] = FetchKeysInput

    store: KVStateStore = Field(exclude=True)

    def _run(self) -> str:
        keys = self.store.get_keys()
        if not keys:
            return "当前没有可用的keys"
        return "可用的keys:\n" + "\n".join(keys)


class WriteTool(BaseTool):
    """写入状态工具 - patch_state的简化别名"""
    name: str = "write"
    description: str = (
        "修改KV状态。支持 ADD(添加), MOD(修改), DEL(删除) 操作。"
        "value 必须是完整的自然语言段落。"
    )
    args_schema: type[BaseModel] = WriteInput

    store: KVStateStore = Field(exclude=True)

    def _run(self, operations: list[dict]) -> str:
        success, changes = self.store.patch(operations)

        if not changes:
            return "未应用任何变更"

        lines = []
        for c in changes:
            if c.operation == "ADD":
                lines.append(f"✓ ADD [{c.key}]")
            elif c.operation == "MOD":
                lines.append(f"✓ MOD [{c.key}]")
            elif c.operation == "DEL":
                lines.append(f"✓ DEL [{c.key}]")

        status = "成功" if success else "部分失败"
        return f"[{status}] 应用了 {len(changes)} 个变更:\n" + "\n".join(lines)


# ============================================
# 工具箱
# ============================================

class TrpgToolkit(BaseToolkit):
    """TRPG 极简工具箱 - 仅包含 4 个核心工具"""

    def __init__(self, world_state_path: str = "data/world_state.txt", persist: bool = False, **kwargs):
        self._store = KVStateStore(world_state_path, persist=persist)
        self._logic_engine = LogicEngine()
        self._retriever = Retriever(**kwargs)

    @property
    def store(self) -> KVStateStore:
        return self._store

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
            EvaluateTool(logic_engine=self._logic_engine),
            GetStateTool(store=self._store),
            PatchStateTool(store=self._store),
            ReadTool(store=self._store),
            FetchKeysTool(store=self._store),
            WriteTool(store=self._store),
        ]
