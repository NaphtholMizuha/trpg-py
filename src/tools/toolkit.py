"""
TrpgToolkit - 极简工具箱
仅包含 5 个核心工具:
- search: RAG 检索
- evaluate: 执行 Roll() 表达式
- fetch_keys: 获取所有 key 列表
- read: 读取指定 key(s) 的值
- write: ADD/MOD/DEL 状态变更
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


class ReadInput(BaseModel):
    """读取状态工具输入"""
    keys: list[str] = Field(
        description="要读取的状态键列表，如 ['Aldera.combat', 'Goblin.status']。"
                    "支持批量读取多个key。"
    )


class FetchKeysInput(BaseModel):
    """获取所有key列表工具输入"""
    pass


class WriteInput(BaseModel):
    """写入状态工具输入"""
    operations: list[dict] = Field(
        description="操作列表，支持 ADD(添加), MOD(修改), DEL(删除)。"
                    "示例: [{\"op\": \"MOD\", \"key\": \"Aldera.combat\", \"value\": \"HP: 38/44...\"}]"
    )


class WriteFieldsInput(BaseModel):
    """批量写入字段变更工具输入"""
    field_changes: list[dict] = Field(
        description="字段级变更列表。每个变更包含: key, field, old_value, new_value, operation。"
                    "示例: [{\"key\": \"Aldera.combat\", \"field\": \"HP\", \"old_value\": \"44/44\", \"new_value\": \"38/44\", \"operation\": \"MOD\"}]"
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


class ReadTool(BaseTool):
    """读取状态工具 - 读取指定key(s)的KV记忆value

    使用场景：
    - 获取单个key: keys=["Aldera.combat"]
    - 批量获取: keys=["Aldera.combat", "Goblin.status"]
    - 获取所有: 先调用 fetch_keys，再用 read 批量获取
    """
    name: str = "read"
    description: str = """读取指定key(s)的KV记忆value。

使用场景：
- 获取单个key: keys=["Aldera.combat"]
- 批量获取: keys=["Aldera.combat", "Goblin.status"]
- 获取所有: 先调用 fetch_keys，再用 read 批量获取
"""
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
    """写入状态工具 - 修改KV状态

    支持 ADD(添加), MOD(修改), DEL(删除) 操作。
    value 必须是完整的自然语言段落。
    """
    name: str = "write"
    description: str = """修改KV状态。支持 ADD(添加), MOD(修改), DEL(删除) 操作。

使用示例:
- 修改状态: [{"op": "MOD", "key": "Aldera.combat", "value": "HP: 38/44 | AC: 18..."}]
- 添加新key: [{"op": "ADD", "key": "NewNPC.combat", "value": "HP: 20/20..."}]
- 删除key: [{"op": "DEL", "key": "DefeatedEnemy.combat"}]

注意: value 必须是完整的自然语言段落，不是单个字段。
"""
    args_schema: type[BaseModel] = WriteInput

    store: KVStateStore = Field(exclude=True)

    def _run(self, operations: list[dict]) -> str:
        success, changes = self.store.patch(operations)

        if not changes:
            return "未应用任何变更"

        lines = []
        for c in changes:
            if c.operation == "ADD":
                new_preview = (c.new_value[:50] + "...") if c.new_value else "None"
                lines.append(f"✓ ADD [{c.key}] = {new_preview}")
            elif c.operation == "MOD":
                old_preview = (c.old_value[:30] + "...") if c.old_value else "None"
                new_preview = (c.new_value[:50] + "...") if c.new_value else "None"
                lines.append(f"✓ MOD [{c.key}]: {old_preview} → {new_preview}")
            elif c.operation == "DEL":
                old_preview = (c.old_value[:50] + "...") if c.old_value else "None"
                lines.append(f"✓ DEL [{c.key}] (原值: {old_preview})")

        status = "成功" if success else "部分失败"
        return f"[{status}] 应用了 {len(changes)} 个变更:\n" + "\n".join(lines)


class WriteFieldsTool(BaseTool):
    """批量写入字段变更工具 - Executor使用

    接收字段级变更列表，自动读取当前值、应用变更、写回KV。
    相当于将原Writer节点的功能封装为工具。
    """
    name: str = "write_fields"
    description: str = """批量应用字段级变更到KV状态。

使用场景：Executor执行计算后，将生成的字段变更写入状态。

参数格式:
field_changes: [
  {"key": "Aldera.combat", "field": "HP", "old_value": "44/44", "new_value": "38/44", "operation": "MOD"},
  {"key": "Goblin.status", "field": "状态", "old_value": "存活", "new_value": "死亡", "operation": "MOD"}
]

注意:
- 工具会自动读取当前完整值，应用字段变更，然后写回
- 无需手动构建完整的value，只需指定字段变更
- operation支持: MOD(修改), DEL(删除字段)
"""
    args_schema: type[BaseModel] = WriteFieldsInput

    store: KVStateStore = Field(exclude=True)

    def _run(self, field_changes: list[dict]) -> str:
        from ..utils.kv_patch import KVPatch

        if not field_changes:
            return "无字段变更需要应用"

        applied_count = 0
        lines = []

        for fc in field_changes:
            try:
                # 支持 key+field 或 path 两种格式
                key = fc.get("key", "")
                field = fc.get("field", "")
                path = fc.get("path", "")

                # 如果提供了 path，从中提取 key 和 field
                if path and not key:
                    parts = path.rsplit(".", 1)
                    if len(parts) == 2:
                        key, field = parts
                    else:
                        key = path
                        field = ""

                old_value = fc.get("old_value", "")
                new_value = fc.get("new_value", "")
                operation = fc.get("operation", "MOD")

                # 读取当前完整值
                current_full = self.store.get(key) or ""

                # 应用补丁
                patch = KVPatch(current_full)

                if operation == "DEL":
                    patch.remove_field(field)
                else:
                    patch.set_field(field, new_value)

                new_full = patch.to_string()

                # 写回 KV
                self.store.set(key, new_full)

                applied_count += 1
                lines.append(f"✓ {key}.{field}: {old_value} → {new_value}")

            except Exception as e:
                err_key = key or fc.get('key', '?') or fc.get('path', '?')
                err_field = field or fc.get('field', '?')
                lines.append(f"✗ {err_key}.{err_field}: 失败 - {e}")

        return f"[成功] 应用了 {applied_count}/{len(field_changes)} 个字段变更:\n" + "\n".join(lines)


# ============================================
# 工具箱
# ============================================

class TrpgToolkit(BaseToolkit):
    """TRPG 极简工具箱 - 仅包含 5 个核心工具"""

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
            FetchKeysTool(store=self._store),
            ReadTool(store=self._store),
            WriteTool(store=self._store),
            WriteFieldsTool(store=self._store),
        ]
