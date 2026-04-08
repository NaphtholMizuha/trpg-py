from __future__ import annotations

import unittest

from augury.agent.tools.ask import AskInterrupt, create_ask_tool


class AskToolTests(unittest.TestCase):
    def test_ask_tool_raises_interrupt_when_no_response_is_available(self) -> None:
        tool = create_ask_tool()

        with self.assertRaises(AskInterrupt) as captured:
            tool.invoke(
                {
                    "question_id": "target",
                    "prompt": "请选择目标",
                    "options": [
                        {"id": "goblin_1", "label": "goblin_1", "description": "最近的 goblin"},
                        {"id": "goblin_2", "label": "goblin_2"},
                    ],
                    "default_option_id": "goblin_1",
                    "allow_custom_input": True,
                    "custom_input_label": "输入自定义目标",
                    "custom_input_placeholder": "例如 goblin_3",
                    "reason": "目标描述有歧义",
                }
            )

        request = captured.exception.request
        self.assertEqual("target", request.question_id)
        self.assertEqual("goblin_1", request.default_option_id)
        self.assertTrue(request.allow_custom_input)
        self.assertEqual("输入自定义目标", request.custom_input_label)
        self.assertEqual(2, len(request.options))

    def test_ask_tool_returns_response_when_resume_payload_is_supplied(self) -> None:
        tool = create_ask_tool()

        result = tool.invoke(
            {
                "question_id": "target",
                "prompt": "请选择目标",
                "resume_response": {"question_id": "target", "selected_option_id": "goblin_2"},
            }
        )

        self.assertEqual("target", result["question_id"])
        self.assertEqual("goblin_2", result["selected_option_id"])


if __name__ == "__main__":
    unittest.main()
