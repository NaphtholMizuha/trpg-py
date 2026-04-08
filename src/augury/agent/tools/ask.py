from __future__ import annotations

from typing import Any, Callable

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from augury.agent.models import AskRequest, AskResponse


class AskOptionInput(BaseModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str | None = None


class AskInput(BaseModel):
    question_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    options: list[AskOptionInput] = Field(default_factory=list)
    default_option_id: str | None = None
    allow_custom_input: bool = False
    custom_input_label: str | None = None
    custom_input_placeholder: str | None = None
    reason: str | None = None
    resume_response: dict[str, Any] | None = None


class AskInterrupt(Exception):
    def __init__(self, request: AskRequest) -> None:
        super().__init__(request.prompt)
        self.request = request


class AskTool(BaseTool):
    name: str = "ask"
    description: str = "发起一个可中断的 ask 请求，并在恢复后返回结构化回答。"
    args_schema: type[BaseModel] = AskInput
    responder: Callable[[AskRequest], AskResponse | dict[str, Any]] | None = None

    def _run(
        self,
        question_id: str,
        prompt: str,
        options: list[Any] | None = None,
        default_option_id: str | None = None,
        allow_custom_input: bool = False,
        custom_input_label: str | None = None,
        custom_input_placeholder: str | None = None,
        reason: str | None = None,
        resume_response: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_options = [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in (options or [])
        ]
        request = AskRequest(
            question_id=question_id,
            prompt=prompt,
            options=normalized_options,
            default_option_id=default_option_id,
            allow_custom_input=allow_custom_input,
            custom_input_label=custom_input_label,
            custom_input_placeholder=custom_input_placeholder,
            reason=reason,
        )
        if resume_response is not None:
            response = AskResponse.model_validate(resume_response)
            return response.model_dump()
        if self.responder is not None:
            response = self.responder(request)
            return AskResponse.model_validate(response).model_dump()
        raise AskInterrupt(request)


def create_ask_tool(
    responder: Callable[[AskRequest], AskResponse | dict[str, Any]] | None = None,
) -> AskTool:
    return AskTool(responder=responder)
