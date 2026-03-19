"""
Agent 基类 - 封装项目级 agent 调用约定

将通用 ReAct 工具循环下沉给 LangChain agent runtime，
BaseAgent 只保留模型创建、统一调用入口和结构化输出兜底。
"""
from abc import ABC, abstractmethod
from typing import Any, TypeVar, cast
import json
import os
import re

from langchain.agents import create_agent
from langchain.agents.structured_output import StructuredOutputValidationError, ToolStrategy
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel

from ..utils.logging import get_logger
from .exceptions import LLMError, ParseError

logger = get_logger(__name__)

StructuredOutputT = TypeVar("StructuredOutputT", bound=BaseModel)
DEFAULT_FORCE_OUTPUT_PROMPT = "请直接输出最终结果，不要继续调用工具。"


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


def _full_text(content: Any) -> str:
    text = _content_to_text(content)
    return text if text else "<empty>"


def _serialize_ai_message(ai_message: AIMessage) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "type": ai_message.__class__.__name__,
        "id": getattr(ai_message, "id", None),
        "name": getattr(ai_message, "name", None),
        "content": getattr(ai_message, "content", None),
        "tool_calls": getattr(ai_message, "tool_calls", None),
        "invalid_tool_calls": getattr(ai_message, "invalid_tool_calls", None),
        "additional_kwargs": getattr(ai_message, "additional_kwargs", None),
        "response_metadata": getattr(ai_message, "response_metadata", None),
        "usage_metadata": getattr(ai_message, "usage_metadata", None),
    }
    return snapshot


def _extract_final_ai_message(messages: list[Any]) -> AIMessage:
    """从消息列表中提取最终的 AI 消息。"""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            if isinstance(msg.content, str) and msg.content.strip():
                return msg
            if isinstance(msg.content, list) and msg.content:
                return msg
    raise LLMError("No AI message found in agent response")


class BaseAgent(ABC):
    """Agent 基类 - 封装项目级 agent 调用约定。"""

    def __init__(
        self,
        model: str,
        api_key: str | None,
        base_url: str | None,
        tools: list[BaseTool] | None,
        max_iterations: int = 10,
    ):
        self.model_name = model
        self.api_key = api_key
        self.base_url = base_url
        self.tools = {t.name: t for t in (tools or [])}
        self._tools = list(tools or [])
        self.llm = self._create_llm(model, api_key, base_url)
        self.max_iterations = max_iterations
        self._logger = get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    def _create_llm(self, model: str, api_key: str | None, base_url: str | None) -> ChatOpenAI:
        """创建 LLM 实例。"""
        if not api_key and not base_url and not os.getenv("OPENAI_API_KEY"):
            raise ValueError("未提供 API key，且环境变量 OPENAI_API_KEY 未设置")
        if not api_key and base_url and not os.getenv("OPENAI_API_KEY"):
            raise ValueError(f"未提供 API key，无法初始化 OpenAI 兼容模型客户端 (base_url={base_url})")
        kwargs: dict[str, Any] = {"model": model, "temperature": 0, "api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)

    def _build_agent(
        self,
        *,
        tools: list[BaseTool] | None = None,
        response_format: type[StructuredOutputT] | None = None,
        system_prompt: str | None = None,
    ):
        """构造项目统一使用的 LangChain agent。"""
        kwargs: dict[str, Any] = {
            "model": self.llm,
            "tools": list(self._tools if tools is None else tools),
        }
        if response_format is not None:
            kwargs["response_format"] = ToolStrategy(schema=response_format)
        if system_prompt is not None:
            kwargs["system_prompt"] = system_prompt
        return create_agent(**kwargs)

    def _get_recursion_limit(self) -> int:
        """将旧的 max_iterations 近似映射到 agent graph 递归上限。"""
        return max(4, self.max_iterations * 2 + 1)

    def _log_structured_output_validation_error(self, exc: StructuredOutputValidationError) -> None:
        ai_message = getattr(exc, "ai_message", None)
        if ai_message is None:
            return

        content = getattr(ai_message, "content", None)
        ai_message_snapshot = _serialize_ai_message(ai_message)
        self._logger.error(
            "Structured output 原始响应（完整文本）",
            tool_name=getattr(exc, "tool_name", None),
            raw_response=_full_text(content),
            raw_response_repr=repr(content),
        )
        self._logger.error(
            "Structured output 原始 AIMessage（完整对象）",
            tool_name=getattr(exc, "tool_name", None),
            ai_message=ai_message_snapshot,
            ai_message_repr=repr(ai_message),
        )

    def _invoke_agent(
        self,
        *,
        messages: list,
        tools: list[BaseTool] | None = None,
        response_format: type[StructuredOutputT] | None = None,
        force_output_prompt: str | None = None,
        system_prompt: str | None = None,
    ) -> StructuredOutputT | AIMessage:
        """统一的 agent 调用入口。"""
        agent = self._build_agent(
            tools=tools,
            response_format=response_format,
            system_prompt=system_prompt,
        )
        try:
            result = cast(
                dict[str, Any],
                agent.invoke(
                    {"messages": messages},
                    config={"recursion_limit": self._get_recursion_limit()},
                ),
            )
        except GraphRecursionError as exc:
            self._logger.warning(f"agent 达到最大迭代次数，将尝试强制收口: {exc}")
            if response_format is not None:
                forced_messages = list(messages)
                if force_output_prompt:
                    forced_messages.append(HumanMessage(content=force_output_prompt))
                return self._invoke_structured_output(forced_messages, response_format)
            forced_prompt = force_output_prompt or DEFAULT_FORCE_OUTPUT_PROMPT
            try:
                return cast(AIMessage, self.llm.invoke([*messages, HumanMessage(content=forced_prompt)]))
            except Exception as inner_exc:
                raise LLMError(f"Agent 调用超过最大迭代次数，且强制收口失败: {inner_exc}") from inner_exc
        except StructuredOutputValidationError as exc:
            self._log_structured_output_validation_error(exc)
            raise LLMError(f"Agent 调用失败: {exc}") from exc
        except Exception as exc:
            raise LLMError(f"Agent 调用失败: {exc}") from exc

        if response_format is not None:
            structured_result = result.get("structured_response")
            if structured_result is not None:
                return self._require_structured_result(structured_result, response_format)

            forced_messages = list(messages)
            if force_output_prompt:
                forced_messages.append(HumanMessage(content=force_output_prompt))
            self._logger.warning("agent 未返回 structured_response，将回退到 provider 结构化输出")
            return self._invoke_structured_output(forced_messages, response_format)

        return _extract_final_ai_message(cast(list[Any], result.get("messages", messages)))

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
            self._logger.warning(f"json_schema structured output 失败，回退 function_calling: {exc}")
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

        try:
            raw_response = cast(AIMessage, self.llm.invoke(messages))
        except Exception as exc:
            raise LLMError(f"原始 LLM 调用失败: {exc}") from exc

        raw_text = _content_to_text(raw_response.content)
        self._logger.warning(
            "structured output 原始返回如下，将尝试手工解析:\n" + _preview_text(raw_text)
        )
        json_payload = _extract_json_payload(raw_response.content)
        if not json_payload:
            raise ParseError(raw_text, "未能从模型输出中提取 JSON")

        self._logger.warning("structured output 提取出的 JSON:\n" + _preview_text(json_payload))
        try:
            return schema.model_validate(json.loads(json_payload))
        except Exception as exc:
            raise ParseError(json_payload, f"JSON 解析或校验失败: {exc}") from exc

    def _require_structured_result(
        self,
        result: Any,
        schema: type[StructuredOutputT],
    ) -> StructuredOutputT:
        if result is None:
            raise ValueError(f"{schema.__name__} structured output returned None")
        return cast(StructuredOutputT, result)

    @abstractmethod
    def get_system_prompt(self) -> str:
        """获取系统提示词，子类必须实现。"""
        pass
