from __future__ import annotations

from typing import Callable

from augury.agent.models import AskRequest, AskResponse


def prompt_for_ask_requests(
    requests: list[AskRequest],
    *,
    input_func: Callable[[str], str] = input,
) -> list[AskResponse]:
    responses: list[AskResponse] = []
    for request in requests:
        responses.append(_prompt_for_request(request, input_func=input_func))
    return responses


def _prompt_for_request(
    request: AskRequest,
    *,
    input_func: Callable[[str], str],
) -> AskResponse:
    options_by_id = {option.id: option for option in request.options}
    option_ids = [option.id for option in request.options]

    while True:
        _print_request(request)
        answer = input_func("选择选项 ID，直接回车使用默认值，或输入 custom:你的答案: ").strip()
        if not answer:
            if request.default_option_id is not None:
                return AskResponse(question_id=request.question_id, selected_option_id=request.default_option_id)
            if request.allow_custom_input:
                custom_value = input_func(_build_custom_prompt(request)).strip()
                if custom_value:
                    return AskResponse(question_id=request.question_id, custom_input=custom_value)
            continue
        if answer in option_ids:
            return AskResponse(question_id=request.question_id, selected_option_id=answer)
        if request.allow_custom_input and answer.startswith("custom:"):
            custom_value = answer.split("custom:", maxsplit=1)[1].strip()
            if not custom_value:
                custom_value = input_func(_build_custom_prompt(request)).strip()
            if custom_value:
                return AskResponse(question_id=request.question_id, custom_input=custom_value)
        if request.allow_custom_input and answer not in options_by_id:
            return AskResponse(question_id=request.question_id, custom_input=answer)
        print("无效输入，请重试。")


def _print_request(request: AskRequest) -> None:
    print("")
    print(f"DM Ask: {request.prompt}")
    if request.reason:
        print(f"reason: {request.reason}")
    if request.options:
        print("options:")
        for option in request.options:
            suffix = " (default)" if option.id == request.default_option_id else ""
            line = f"- {option.id}: {option.label}{suffix}"
            if option.description:
                line += f" | {option.description}"
            print(line)
    if request.allow_custom_input:
        print("custom_input: allowed")


def _build_custom_prompt(request: AskRequest) -> str:
    label = request.custom_input_label or "请输入自定义答案"
    placeholder = request.custom_input_placeholder or ""
    suffix = f" ({placeholder})" if placeholder else ""
    return f"{label}{suffix}: "

