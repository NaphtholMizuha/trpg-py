"""
Agent 基类 - 封装 ReAct 循环和工具调用逻辑

消除三个 Agent 之间的代码重复
"""
from abc import ABC, abstractmethod
from typing import Any, TypeVar, cast
import json
import os
import re

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from ..utils.logging import get_logger

logger = get_logger(__name__)

StructuredOutputT = TypeVar("StructuredOutputT", bound=BaseModel)


def _extract_json_payload(content: Any) -> str | None:
    """从模型输出中提取 JSON，兼容 fenced code block。"""
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        content = "\n".join(text_parts)

    if not isinstance(content, str):
        return None

    text = content.strip()
    if not text:
        return None

    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and start < end:
        return text[start:end + 1].strip()

    return None


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
            else:
                text_parts.append(str(item))
        return "\n".join(text_parts)
    return str(content)


def _preview_text(text: str, limit: int = 1500) -> str:
    preview = text.strip()
    if len(preview) <= limit:
        return preview
    return preview[:limit].rstrip() + "\n... [截断]"


class BaseAgent(ABC):
    """Agent 基类 - 封装 ReAct 循环和工具调用逻辑"""

    CACHEABLE_TOOLS: set[str] = set()

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
        self._tool_cache: dict[str, str] = {}
        self._logger = get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    def _create_llm(self, model: str, api_key: str | None, base_url: str | None) -> ChatOpenAI:
        """创建 LLM 实例"""
        if not api_key and not base_url and not os.getenv("OPENAI_API_KEY"):
            raise ValueError("未提供 API key，且环境变量 OPENAI_API_KEY 未设置")
        if not api_key and base_url and not os.getenv("OPENAI_API_KEY"):
            raise ValueError(f"未提供 API key，无法初始化 OpenAI 兼容模型客户端 (base_url={base_url})")
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

    def _react_loop_structured(
        self,
        messages: list,
        schema: type[StructuredOutputT],
        force_output_prompt: str = "请直接输出结构化结果",
    ) -> StructuredOutputT:
        """执行工具循环后，用结构化输出生成最终结果。"""
        response: AIMessage | None = None
        for i in range(self.max_iterations):
            response = cast(AIMessage, self.llm_with_tools.invoke(messages))
            messages.append(response)

            if not response.tool_calls:
                break

            for tool_call in response.tool_calls:
                result = self._execute_tool(tool_call)
                messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))

        if response is None:
            raise RuntimeError("No AI response found in structured react loop")

        if self._should_force_output(i, response):
            messages.append(HumanMessage(content=force_output_prompt))
        else:
            messages.append(HumanMessage(content=force_output_prompt))

        return self._invoke_structured_output(messages, schema)

    def _invoke_structured_output(
        self,
        messages: list,
        schema: type[StructuredOutputT],
    ) -> StructuredOutputT:
        """优先使用 provider 原生 json schema，失败时逐步回退。"""
        try:
            return self._require_structured_result(
                self.llm.with_structured_output(schema, method="json_schema").invoke(messages),
                schema,
            )
        except Exception as exc:
            self._logger.warning(f"json_schema structured output 失败，回退默认模式: {exc}")
        try:
            return self._require_structured_result(
                self.llm.with_structured_output(schema, method="function_calling").invoke(messages),
                schema,
            )
        except Exception as exc:
            self._logger.warning(f"function_calling structured output 失败，回退默认模式: {exc}")
        try:
            return self._require_structured_result(
                self.llm.with_structured_output(schema).invoke(messages),
                schema,
            )
        except Exception as exc:
            self._logger.warning(f"default structured output 失败，尝试手工解析: {exc}")

        raw_response = cast(AIMessage, self.llm.invoke(messages))
        raw_text = _content_to_text(raw_response.content)
        self._logger.warning(
            "structured output 原始返回如下，将尝试手工解析:\n" + _preview_text(raw_text)
        )
        json_payload = _extract_json_payload(raw_response.content)
        if not json_payload:
            raise ValueError("未能从模型输出中提取 JSON")
        self._logger.warning("structured output 提取出的 JSON:\n" + _preview_text(json_payload))
        return schema.model_validate(json.loads(json_payload))

    def _require_structured_result(
        self,
        result: Any,
        schema: type[StructuredOutputT],
    ) -> StructuredOutputT:
        if result is None:
            raise ValueError(f"{schema.__name__} structured output returned None")
        return cast(StructuredOutputT, result)

    def _execute_tool(self, tool_call: Any) -> str:
        """执行单个工具调用"""
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call.get("id", "unknown")

        # 高层级：工具调用事件
        self._logger.info(f"▶ 调用工具 [{tool_name}]")

        # 低层级：输入参数
        self._logger.debug(f"  参数: {tool_args}")

        cache_key = self._build_tool_cache_key(tool_name, tool_args)
        if cache_key is not None and cache_key in self._tool_cache:
            cached = self._tool_cache[cache_key]
            display_result = cached if len(cached) <= 500 else cached[:500] + "\n  ... [缓存截断]"
            self._logger.debug(f"  命中缓存: {display_result}")
            return cached

        if tool_name in self.tools:
            try:
                result = self.tools[tool_name].invoke(tool_args)
                result_str = str(result)

                # 截断过长结果用于日志显示
                display_result = result_str
                if len(display_result) > 500:
                    display_result = display_result[:500] + "\n  ... [截断]"

                # 低层级：输出结果
                self._logger.debug(f"  结果: {display_result}")
                if cache_key is not None:
                    self._tool_cache[cache_key] = result_str
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

    def _build_tool_cache_key(self, tool_name: str, tool_args: Any) -> str | None:
        if tool_name not in self.CACHEABLE_TOOLS:
            return None
        try:
            normalized = json.dumps(tool_args, ensure_ascii=False, sort_keys=True)
        except TypeError:
            normalized = repr(tool_args)
        return f"{tool_name}:{normalized}"

    @abstractmethod
    def get_system_prompt(self) -> str:
        """获取系统提示词，子类必须实现"""
        pass
