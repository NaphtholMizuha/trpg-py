"""
DND DM 辅助 Agent - 基于 LangGraph 的游戏主持助手

节点流程:
1. 意图分析: DM描述 → 结构化任务入队
2. 规则获取: 出队任务 → RAG查询规则
3. 逻辑判定: 根据规则+schema → 构造表达式 → 执行
4. 状态更新: 解析结果 → 更新世界状态
5. 连锁检测: 检测状态更新影响 → 新任务入队（需DM审批）
6. 队列空则结束
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from ..tools.toolkit import TrpgToolkit


# ============================================
# 结构化任务定义
# ============================================

class Task(BaseModel):
    """结构化任务"""
    id: str = Field(description="任务唯一标识")
    description: str = Field(description="任务描述")
    type: Literal["action", "query", "update", "chain"] = Field(description="任务类型")
    requires_approval: bool = Field(default=False, description="是否需要DM审批")
    approved: bool | None = Field(default=None, description="审批状态: None=待审批, True=已批准, False=已拒绝")
    context: dict[str, Any] = Field(default_factory=dict, description="任务上下文")


class StateUpdate(BaseModel):
    """状态更新记录"""
    path: str = Field(description="状态路径")
    old_value: Any = Field(description="旧值")
    new_value: Any = Field(description="新值")
    reason: str = Field(description="更新原因")


# ============================================
# Agent State
# ============================================

class AgentState(BaseModel):
    """Agent 状态"""
    # 消息历史
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    # 任务队列
    task_queue: list[Task] = Field(default_factory=list)
    current_task: Task | None = Field(default=None)

    # 规则上下文 (RAG检索结果)
    rules_context: str = Field(default="")

    # 表达式执行结果
    expression_results: list[dict[str, Any]] = Field(default_factory=list)

    # 状态更新记录
    state_updates: list[StateUpdate] = Field(default_factory=list)

    # 控制流标志
    pending_approval: bool = Field(default=False)
    awaiting_dm_input: bool = Field(default=True)

    # 输出给DM的信息
    dm_output: str = Field(default="")


# ============================================
# LLM Prompts
# ============================================

INTENT_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是D&D 5e游戏主持助手。你的任务是将DM的自然语言描述转换为结构化的任务。

当前世界状态Schema:
{schema}

当前任务队列:
{task_queue}

根据DM的输入，分析其意图并创建结构化任务。任务类型:
- action: 需要执行游戏机制的动作（如攻击、技能检定、豁免检定）
- query: 纯查询任务（如查询规则、查询状态）
- update: 直接更新状态的任务
- chain: 连锁反应任务（由其他任务触发的后续任务）

输出JSON格式:
{{
    "tasks": [
        {{
            "id": "task_1",
            "description": "张三使用长剑攻击哥布林",
            "type": "action",
            "requires_approval": false,
            "context": {{"attacker": "张三", "target": "哥布林", "weapon": "长剑"}}
        }}
    ]
}}"""),
    ("human", "{dm_input}")
])

RULE_RETRIEVAL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是D&D 5e规则助手。根据当前任务，构造合适的RAG查询来获取相关规则。

当前任务:
{task}

已检索到的规则上下文:
{rules_context}

请生成一个或多个查询关键词来获取完成任务所需的规则。输出JSON格式:
{{
    "queries": ["攻击动作规则", "长剑属性", "攻击检定"]
}}"""),
    ("human", "请生成查询关键词")
])

LOGIC_EVALUATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是D&D 5e游戏机制执行引擎。根据任务和规则上下文，构造并执行游戏机制表达式。

当前任务:
{task}

规则上下文:
{rules_context}

世界状态Schema:
{schema}

可用表达式语法:
- Roll("XdY"): 掷骰，如 Roll("1d20") 或 Roll("2d6")
- 状态路径引用: 直接使用schema中的路径，如 entity.players.player_01.attributes.modifiers.strength
- 比较操作符: >, <, ==, >=, <=, !=
- 算术操作符: +, -, *, /

重要：路径必须与Schema中的结构完全一致！

输出JSON格式:
{{
    "expressions": [
        {{
            "description": "攻击检定",
            "expression": "Roll('1d20') + entity.players.player_01.attributes.modifiers.strength + entity.players.player_01.proficiency.bonus >= 目标.ac",
            "purpose": "判定攻击是否命中"
        }}
    ]
}}"""),
    ("human", "请构造表达式")
])

STATE_UPDATE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是D&D 5e状态管理助手。根据表达式执行结果，更新世界状态。

当前任务:
{task}

表达式执行结果:
{expression_results}

当前世界状态Schema:
{schema}

请生成状态更新操作。输出JSON格式:
{{
    "patches": [
        {{
            "op": "subtract",
            "path": "entities.哥布林.hp",
            "value": 8,
            "reason": "张三的长剑攻击造成8点伤害"
        }}
    ]
}}"""),
    ("human", "请生成状态更新")
])

CHAIN_DETECTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是D&D 5e连锁反应检测器。分析状态更新可能带来的后续影响。

状态更新记录:
{state_updates}

当前世界状态Schema:
{schema}

检测是否有需要后续处理的连锁反应，如:
- 实体HP <= 0 → 死亡判定
- 状态变化 → 触发条件效果
- 战斗结束 → 战利品分配

输出JSON格式:
{{
    "chain_tasks": [
        {{
            "id": "chain_1",
            "description": "张三HP归零，进行死亡判定",
            "type": "chain",
            "requires_approval": true,
            "context": {{"entity": "张三", "trigger": "hp_zero"}}
        }}
    ]
}}"""),
    ("human", "检测连锁反应")
])


# ============================================
# Node Functions
# ============================================

def create_intent_analysis_node(toolkit: TrpgToolkit, llm):
    """创建意图分析节点"""
    async def intent_analysis(state: AgentState) -> dict:
        if not state.awaiting_dm_input or not state.messages:
            return {"dm_output": "等待DM输入..."}

        # 获取最后一条用户消息
        last_message = state.messages[-1]
        if not isinstance(last_message, HumanMessage):
            return {"dm_output": "等待DM输入..."}

        dm_input = last_message.content
        schema = json.dumps(toolkit.state_manager.get_schema(), ensure_ascii=False, indent=2)
        task_queue_str = json.dumps([t.model_dump() for t in state.task_queue], ensure_ascii=False, indent=2)

        # 调用LLM分析意图
        response = await llm.ainvoke(
            INTENT_ANALYSIS_PROMPT.format(
                schema=schema,
                task_queue=task_queue_str,
                dm_input=dm_input
            )
        )

        # 解析LLM响应
        try:
            content = response.content
            # 提取JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())
            new_tasks = [Task(**t) for t in result.get("tasks", [])]

            # 添加到任务队列
            updated_queue = state.task_queue + new_tasks

            return {
                "task_queue": updated_queue,
                "awaiting_dm_input": False,
                "dm_output": f"已创建 {len(new_tasks)} 个任务:\n" + "\n".join(f"- {t.description}" for t in new_tasks)
            }
        except (json.JSONDecodeError, KeyError) as e:
            return {"dm_output": f"意图解析失败: {e}"}

    return intent_analysis


def create_rule_retrieval_node(toolkit: TrpgToolkit, llm):
    """创建规则获取节点"""

    async def rule_retrieval(state: AgentState) -> dict:
        if not state.task_queue:
            return {"dm_output": "任务队列为空"}

        # 取出第一个任务
        current_task = state.task_queue[0]
        remaining_queue = state.task_queue[1:]

        # 调用LLM生成查询关键词
        response = await llm.ainvoke(
            RULE_RETRIEVAL_PROMPT.format(
                task=current_task.model_dump(),
                rules_context=state.rules_context
            )
        )

        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())
            queries = result.get("queries", [])
        except (json.JSONDecodeError, KeyError):
            queries = [current_task.description]

        # 执行RAG查询
        all_results = []
        for query in queries[:3]:  # 最多3个查询
            results = toolkit.retriever.search(query, limit=2)
            all_results.extend(results)

        # 合并规则上下文
        rules_context = "\n\n".join(
            f"[{r.get('metadata', {}).get('title', '规则')}]\n{r.get('content', '')}"
            for r in all_results[:5]  # 最多5条
        )

        return {
            "current_task": current_task,
            "task_queue": remaining_queue,
            "rules_context": rules_context,
            "dm_output": f"正在处理任务: {current_task.description}\n已获取规则上下文"
        }

    return rule_retrieval


def create_logic_evaluation_node(toolkit: TrpgToolkit, llm):
    """创建逻辑判定节点"""
    async def logic_evaluation(state: AgentState) -> dict:
        if not state.current_task:
            return {"dm_output": "无当前任务"}

        task = state.current_task
        schema = json.dumps(toolkit.state_manager.get_schema(), ensure_ascii=False, indent=2)

        # 获取表达式求值工具
        eval_tool = None
        for tool in toolkit.get_tools():
            if tool.name == "evaluate_mechanics":
                eval_tool = tool

        # 如果任务类型是query，跳过逻辑判定
        if task.type == "query":
            return {
                "dm_output": f"查询任务完成: {task.description}\n\n规则上下文:\n{state.rules_context}",
                "current_task": None
            }

        # 调用LLM构造表达式
        response = await llm.ainvoke(
            LOGIC_EVALUATION_PROMPT.format(
                task=task.model_dump(),
                rules_context=state.rules_context,
                schema=schema
            )
        )

        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())
            expressions = result.get("expressions", [])
        except (json.JSONDecodeError, KeyError):
            expressions = []

        # 执行表达式
        expression_results = []
        for expr_info in expressions:
            expr = expr_info.get("expression", "")
            try:
                result_str = eval_tool._run(expr) if eval_tool else f"表达式: {expr}"
                expression_results.append({
                    "description": expr_info.get("description", ""),
                    "expression": expr,
                    "result": result_str
                })
            except Exception as e:
                expression_results.append({
                    "description": expr_info.get("description", ""),
                    "expression": expr,
                    "result": f"执行错误: {e}"
                })

        return {
            "expression_results": expression_results,
            "dm_output": "表达式执行完成:\n" + "\n".join(
                f"- {r['description']}: {r['result']}" for r in expression_results
            )
        }

    return logic_evaluation


def create_state_update_node(toolkit: TrpgToolkit, llm):
    """创建状态更新节点"""
    async def state_update(state: AgentState) -> dict:
        if not state.current_task or not state.expression_results:
            return {"dm_output": "无需更新状态"}

        task = state.current_task
        schema = json.dumps(toolkit.state_manager.get_schema(), ensure_ascii=False, indent=2)

        # 获取状态修改工具
        patch_tool = None
        for tool in toolkit.get_tools():
            if tool.name == "modify_state":
                patch_tool = tool

        # 调用LLM生成状态更新
        response = await llm.ainvoke(
            STATE_UPDATE_PROMPT.format(
                task=task.model_dump(),
                expression_results=json.dumps(state.expression_results, ensure_ascii=False, indent=2),
                schema=schema
            )
        )

        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())
            patches = result.get("patches", [])
        except (json.JSONDecodeError, KeyError):
            patches = []

        # 执行状态更新
        state_updates = []
        for patch in patches:
            path = patch.get("path", "")
            op = patch.get("op", "set")
            value = patch.get("value")
            reason = patch.get("reason", "")

            try:
                old_value = toolkit.state_manager.get_or(path, None)
                if patch_tool:
                    patch_tool._run([{"op": op, "path": path, "value": value}])
                new_value = toolkit.state_manager.get_or(path, None)

                state_updates.append(StateUpdate(
                    path=path,
                    old_value=old_value,
                    new_value=new_value,
                    reason=reason
                ))
            except Exception as e:
                state_updates.append(StateUpdate(
                    path=path,
                    old_value=None,
                    new_value=None,
                    reason=f"更新失败: {e}"
                ))

        return {
            "state_updates": state_updates,
            "dm_output": "状态已更新:\n" + "\n".join(
                f"- {u.path}: {u.old_value} → {u.new_value} ({u.reason})" for u in state_updates
            )
        }

    return state_update


def create_chain_detection_node(toolkit: TrpgToolkit, llm):
    """创建连锁检测节点"""
    async def chain_detection(state: AgentState) -> dict:
        if not state.state_updates:
            return {"current_task": None, "dm_output": "任务完成"}

        schema = json.dumps(toolkit.state_manager.get_schema(), ensure_ascii=False, indent=2)

        # 调用LLM检测连锁反应
        response = await llm.ainvoke(
            CHAIN_DETECTION_PROMPT.format(
                state_updates=json.dumps([u.model_dump() for u in state.state_updates], ensure_ascii=False, indent=2),
                schema=schema
            )
        )

        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())
            chain_tasks = [Task(**t) for t in result.get("chain_tasks", [])]
        except (json.JSONDecodeError, KeyError):
            chain_tasks = []

        # 检查是否有需要审批的连锁任务
        needs_approval = [t for t in chain_tasks if t.requires_approval]

        if needs_approval:
            # 将连锁任务添加到队列前面
            updated_queue = chain_tasks + state.task_queue
            return {
                "task_queue": updated_queue,
                "pending_approval": True,
                "current_task": None,
                "dm_output": "检测到连锁反应，需要DM审批:\n" + "\n".join(
                    f"- {t.description}" for t in needs_approval
                )
            }

        # 无需审批的连锁任务直接入队
        if chain_tasks:
            updated_queue = chain_tasks + state.task_queue
            return {
                "task_queue": updated_queue,
                "current_task": None,
                "dm_output": "检测到连锁反应，已自动入队:\n" + "\n".join(
                    f"- {t.description}" for t in chain_tasks
                )
            }

        return {"current_task": None, "dm_output": "任务完成"}

    return chain_detection


# ============================================
# Routing Functions
# ============================================

def route_after_intent(state: AgentState) -> Literal["rule_retrieval", "end"]:
    """意图分析后的路由"""
    if state.task_queue:
        return "rule_retrieval"
    return "end"


def route_after_rule(state: AgentState) -> Literal["logic_evaluation", "rule_retrieval", "end"]:
    """规则获取后的路由"""
    if state.current_task:
        return "logic_evaluation"
    if state.task_queue:
        return "rule_retrieval"  # 继续处理队列
    return "end"


def route_after_logic(state: AgentState) -> Literal["state_update", "rule_retrieval", "end"]:
    """逻辑判定后的路由"""
    # 如果当前任务完成（如query类型），检查队列
    if not state.current_task:
        if state.task_queue:
            return "rule_retrieval"
        return "end"

    # 有表达式结果，进入状态更新
    if state.expression_results:
        return "state_update"

    # 无表达式结果，检查队列
    if state.task_queue:
        return "rule_retrieval"
    return "end"


def route_after_update(state: AgentState) -> Literal["chain_detection", "rule_retrieval", "end"]:
    """状态更新后的路由"""
    if state.state_updates:
        return "chain_detection"
    # 无状态更新，检查队列
    if state.task_queue:
        return "rule_retrieval"
    return "end"


def route_after_chain(state: AgentState) -> Literal["approval_wait", "rule_retrieval", "end"]:
    """连锁检测后的路由"""
    if state.pending_approval:
        return "approval_wait"
    if state.task_queue:
        return "rule_retrieval"
    return "end"


def route_approval(state: AgentState) -> Literal["rule_retrieval", "end"]:
    """审批等待后的路由"""
    # 审批通过或无需审批
    if state.task_queue:
        return "rule_retrieval"
    return "end"


# ============================================
# Graph Builder
# ============================================

def build_dm_agent_graph(toolkit: TrpgToolkit, llm) -> CompiledStateGraph:
    """构建DM Agent图"""
    # 创建节点
    nodes = {
        "intent_analysis": create_intent_analysis_node(toolkit, llm),
        "rule_retrieval": create_rule_retrieval_node(toolkit, llm),
        "logic_evaluation": create_logic_evaluation_node(toolkit, llm),
        "state_update": create_state_update_node(toolkit, llm),
        "chain_detection": create_chain_detection_node(toolkit, llm),
    }

    # 创建图
    builder = StateGraph(AgentState)

    # 添加节点
    for name, node in nodes.items():
        builder.add_node(name, node)

    # 添加审批等待节点（人工节点）
    async def approval_wait(state: AgentState) -> dict:  # noqa: ARG001
        """等待DM审批"""
        return {"dm_output": "等待DM审批连锁任务..."}

    builder.add_node("approval_wait", approval_wait)

    # 设置入口
    builder.set_entry_point("intent_analysis")

    # 添加边
    builder.add_conditional_edges(
        "intent_analysis",
        route_after_intent,
        {"rule_retrieval": "rule_retrieval", "end": END}
    )

    builder.add_conditional_edges(
        "rule_retrieval",
        route_after_rule,
        {"logic_evaluation": "logic_evaluation", "rule_retrieval": "rule_retrieval", "end": END}
    )

    builder.add_conditional_edges(
        "logic_evaluation",
        route_after_logic,
        {"state_update": "state_update", "rule_retrieval": "rule_retrieval", "end": END}
    )

    builder.add_conditional_edges(
        "state_update",
        route_after_update,
        {"chain_detection": "chain_detection", "rule_retrieval": "rule_retrieval", "end": END}
    )

    builder.add_conditional_edges(
        "chain_detection",
        route_after_chain,
        {"approval_wait": "approval_wait", "rule_retrieval": "rule_retrieval", "end": END}
    )

    builder.add_conditional_edges(
        "approval_wait",
        route_approval,
        {"rule_retrieval": "rule_retrieval", "end": END}
    )

    return builder.compile()


# ============================================
# DM Agent 类
# ============================================

class DMAgent:
    """D&D DM 辅助Agent"""

    def __init__(self, llm, initial_state: dict[str, Any] | None = None, **toolkit_kwargs):
        """
        初始化DM Agent

        Args:
            llm: LangChain兼容的LLM实例
            initial_state: 初始世界状态
            **toolkit_kwargs: 传递给TrpgToolkit的参数
        """
        self.toolkit = TrpgToolkit(initial_state=initial_state, **toolkit_kwargs)
        self.llm = llm
        self.graph = build_dm_agent_graph(self.toolkit, llm)
        self._state = AgentState()

    async def process(self, dm_input: str) -> str:
        """
        处理DM输入

        Args:
            dm_input: DM的自然语言输入

        Returns:
            Agent的响应
        """
        # 重置状态并添加用户消息
        self._state = AgentState(
            messages=[HumanMessage(content=dm_input)],
            awaiting_dm_input=True
        )

        # 运行图
        result = await self.graph.ainvoke(self._state)

        # 更新内部状态
        self._state = AgentState(**result)

        return self._state.dm_output

    async def process_stream(self, dm_input: str):
        """
        流式处理DM输入，实时返回节点状态

        Args:
            dm_input: DM的自然语言输入

        Yields:
            tuple: (node_name, state_dict, dm_output)
        """
        # 重置状态并添加用户消息
        self._state = AgentState(
            messages=[HumanMessage(content=dm_input)],
            awaiting_dm_input=True
        )

        # 流式运行图
        async for event in self.graph.astream(self._state, stream_mode="updates"):
            for node_name, node_output in event.items():
                # 更新内部状态
                if node_output:
                    self._state = AgentState(**{**self._state.model_dump(), **node_output})
                dm_output = node_output.get("dm_output", "") if node_output else ""
                yield node_name, node_output, dm_output

    async def approve_chain(self, task_ids: list[str] | None = None) -> str:
        """
        审批连锁任务

        Args:
            task_ids: 批准的任务ID列表，None表示全部批准

        Returns:
            审批结果
        """
        if not self._state.pending_approval:
            return "当前没有待审批的连锁任务"

        # 更新任务审批状态
        updated_queue = []
        for task in self._state.task_queue:
            if task.requires_approval:
                if task_ids is None or task.id in task_ids:
                    task.approved = True
                else:
                    task.approved = False
            updated_queue.append(task)

        self._state.task_queue = [t for t in updated_queue if t.approved is not False]
        self._state.pending_approval = False

        return f"已审批 {len(self._state.task_queue)} 个连锁任务"

    @property
    def world_state(self) -> dict[str, Any]:
        """获取当前世界状态"""
        return self.toolkit.state_manager.snapshot()

    def get_state(self) -> AgentState:
        """获取当前Agent状态"""
        return self._state

    def reset(self, initial_state: dict[str, Any] | None = None):
        """重置Agent"""
        self.toolkit = TrpgToolkit(initial_state=initial_state)
        self.graph = build_dm_agent_graph(self.toolkit, self.llm)
        self._state = AgentState()