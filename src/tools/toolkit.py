"""
TrpgToolkit - 组合 Logic、RAG、State 的 LangChain 工具箱
"""

from typing import Any, Literal

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
        ]