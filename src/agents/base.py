"""
Agent 基类 - 封装 ReAct 循环和工具调用逻辑

消除三个 Agent 之间的代码重复
"""
from abc import ABC, abstractmethod
from typing import Any, cast

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool

from ..utils.logging import get_logger

logger = get_logger(__name__)


class BaseAgent(ABC):
    """Agent 基类 - 封装 ReAct 循环和工具调用逻辑"""

    def __init__(
        self,
        model: str,
        api_key: str | None,
        base_url: str | None,
        tools: list[BaseTool] | None,
        max_iterations: int = 10
    ):
        self.tools = {t.name: t for t in (tools or [])}
        self.llm = self._create_llm(model, api_key, base_url)
        self.llm_with_tools = self.llm.bind_tools(tools) if tools else self.llm
        self.max_iterations = max_iterations
        self._logger = get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    def _create_llm(self, model: str, api_key: str | None, base_url: str | None) -> ChatOpenAI:
        """创建 LLM 实例"""
        kwargs: dict[str, Any] = {"model": model, "temperature": 0, "api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)

    def _react_loop(
        self,
        messages: list,
        force_output_prompt: str = "请直接输出结果",
    ) -> AIMessage:
        """执行 ReAct 循环，返回最终的 AI 消息

        Args:
            messages: 初始消息列表
            force_output_prompt: 强制输出时的提示语

        Returns:
            最终的 AI 消息
        """
        response: AIMessage | None = None
        for i in range(self.max_iterations):
            response = cast(AIMessage, self.llm_with_tools.invoke(messages))
            messages.append(response)

            if not response.tool_calls:
                break

            for tool_call in response.tool_calls:
                result = self._execute_tool(tool_call)
                messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))

        # 强制输出处理
        if response and self._should_force_output(i, response):
            messages.append(HumanMessage(content=force_output_prompt))
            response = cast(AIMessage, self.llm_with_tools.invoke(messages))
            messages.append(response)

        return self._extract_final_message(messages)

    def _execute_tool(self, tool_call: Any) -> str:
        """执行单个工具调用"""
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call.get("id", "unknown")

        # 高层级：工具调用事件
        self._logger.info(f"▶ 调用工具 [{tool_name}]")

        # 低层级：输入参数
        self._logger.debug(f"  参数: {tool_args}")

        if tool_name in self.tools:
            try:
                result = self.tools[tool_name].invoke(tool_args)

                # 截断过长结果用于日志显示
                display_result = str(result)
                if len(display_result) > 500:
                    display_result = display_result[:500] + "\n  ... [截断]"

                # 低层级：输出结果
                self._logger.debug(f"  结果: {display_result}")
                return result
            except Exception as e:
                self._logger.error(f"  ✗ 工具执行错误: {e}")
                return f"错误: {e}"

        self._logger.error(f"  ✗ 未知工具: {tool_name}")
        return f"错误: 未知工具 {tool_name}"

    def _should_force_output(self, iteration: int, response: AIMessage) -> bool:
        """决定是否强制输出

        默认实现：达到最大迭代次数且仍有工具调用时强制输出
        """
        return iteration >= self.max_iterations - 1 and bool(response.tool_calls)

    def _extract_final_message(self, messages: list) -> AIMessage:
        """从消息列表中提取最终的 AI 消息

        默认实现：从后往前找到第一个非空的 AIMessage
        """
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                # 处理 content 可能是 list 的情况
                if isinstance(msg.content, str) and msg.content.strip():
                    return msg
                elif isinstance(msg.content, list) and msg.content:
                    return msg
        raise RuntimeError("No AI message found in response")

    @abstractmethod
    def get_system_prompt(self) -> str:
        """获取系统提示词，子类必须实现"""
        pass
