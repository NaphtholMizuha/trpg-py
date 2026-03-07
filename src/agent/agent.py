from typing import Annotated, TypedDict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages


# ============================================
# 1. 定义 Agent 状态
# ============================================

class AgentState(TypedDict):
    """
    Agent 的状态通过消息列表来维护。
    add_messages 会自动处理新消息的追加，而不会覆盖历史。
    """
    messages: Annotated[list[BaseMessage], add_messages]


# ============================================
# 2. 定义 Agent 逻辑
# ============================================

class DNDAssistantAgent:
    def __init__(
        self,
        toolkit,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0,
        **model_kwargs: Any
    ):
        """
        初始化 D&D 助手 Agent

        Args:
            toolkit: TrpgToolkit 实例
            model: 模型名称，如 "gpt-4o", "deepseek-chat"
            api_key: API 密钥，默认从环境变量读取
            base_url: 自定义 API 基础地址，如 DeepSeek 的 https://api.deepseek.com
            temperature: 温度参数，默认 0
            **model_kwargs: 其他传递给 ChatOpenAI 的参数
        """
        self.toolkit = toolkit
        self.tools = toolkit.get_tools()

        # 初始化 LLM 并绑定工具
        llm_kwargs = {
            "model": model,
            "temperature": temperature,
            **model_kwargs
        }
        if api_key:
            llm_kwargs["api_key"] = api_key
        if base_url:
            llm_kwargs["base_url"] = base_url

        self.llm = ChatOpenAI(**llm_kwargs)
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        # 构建 Graph
        self.graph = self._build_graph()

    def _build_graph(self):
        # 定义 Agent 节点逻辑：调用 LLM
        def agent_node(state: AgentState):
            system_prompt = SystemMessage(content="""
你是一个资深的 D&D 5e DM 助手。你的职责是辅助 DM 管理战役、查阅规则和处理战斗判定。

## 工作流指南
1. **信息收集**：使用 `batch_get` 或 `fetch_schema` 获取实体数据。
2. **规则查阅**：使用 `search` 查询 SRD 文档，用这个工具要使用英文查询。
3. **判定执行**：
   - 掷骰子务必使用 `evaluate_mechanics`，例如 `Roll('1d20')`。
   - 判断命中/通过时，使用比较表达式，例如 `15 > a.b.c`。
   - 你可以直接在表达式中引用状态路径，如 `Roll('1d8') + a.b.c`。
4. **状态更新**：
   - 判定生效后（如伤害），使用 `modify_state` 更新状态。

## 重要原则
- 严谨性：不要凭空编造数值。修改 HP 前必须先进行掷骰计算。
- 格式：计算结果和状态变更要清晰报告给 DM。
            """)

            messages = [system_prompt] + state["messages"]
            response = self.llm_with_tools.invoke(messages)
            return {"messages": [response]}

        # 定义条件边：判断是调用工具还是结束
        def should_continue(state: AgentState):
            last_message = state["messages"][-1]
            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                return "tools"
            return END

        # 构建状态图
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", ToolNode(self.tools))  # ToolNode 自动处理工具调用并将结果追加回消息列表

        # 设置入口
        workflow.set_entry_point("agent")

        # 添加边
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {
                "tools": "tools",
                END: END
            }
        )
        workflow.add_edge("tools", "agent")  # 工具执行完返回 Agent

        return workflow.compile()

    def invoke(self, user_input: str, callback=None) -> str:
        """
        运行 Agent

        Args:
            user_input: 用户输入
            callback: 可选的回调函数，接收 (step, message) 参数用于显示中间步骤
                   step: 步骤序号, message: 当前消息对象
        """
        inputs: AgentState = {"messages": [HumanMessage(content=user_input)]}
        step = 0
        # stream_mode="values" 会输出每一步的状态变更
        for output in self.graph.stream(inputs, stream_mode="values"):
            step += 1
            last_message = output["messages"][-1]
            if callback:
                callback(step, last_message)
        return output["messages"][-1].content

    def stream(self, user_input: str):
        """
        流式运行 Agent，返回每一步的中间消息

        Yields:
            tuple: (step_number, message) 步骤序号和消息对象
        """
        inputs: AgentState = {"messages": [HumanMessage(content=user_input)]}
        step = 0
        for output in self.graph.stream(inputs, stream_mode="values"):
            step += 1
            last_message = output["messages"][-1]
            yield step, last_message


# ============================================
# 3. 便捷工厂函数
# ============================================

def create_deepseek_agent(toolkit, model: str = "deepseek-chat", **kwargs):
    """
    创建使用 DeepSeek API 的 Agent

    Args:
        toolkit: TrpgToolkit 实例
        model: DeepSeek 模型名称，默认 "deepseek-chat"
        **kwargs: 其他配置参数
    """
    return DNDAssistantAgent(
        toolkit=toolkit,
        model=model,
        base_url="https://api.deepseek.com",
        **kwargs
    )
