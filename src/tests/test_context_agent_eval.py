from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from augury.agent import (
    PlannerRequest,
    PlannerDependencies,
    DEFAULT_CONTEXT_AGENT_EVAL_INTENT,
    DEFAULT_CONTEXT_AGENT_EVAL_STATE_FILE,
    build_context_agent_payload,
    mark_cli_ask_interaction_skipped,
    maybe_collect_cli_ask_responses,
    render_context_agent_eval,
    run_context_agent_eval,
)
from augury.agent.utils.cli_ask import prompt_for_ask_requests
from augury.agent.models import AskRequest
from augury.agent.tools.search_stub import create_search_stub_tool
from src.tests.config_helpers import write_project_config
from src.tests.context_agent_helpers import (
    DEFAULT_CONTEXT_AGENT_TEST_USER_PROMPT,
    build_scripted_context_agent_dependencies,
)


class ContextAgentEvalTests(unittest.TestCase):
    def test_build_context_agent_payload_matches_main_agent_delegate_contract(self) -> None:
        payload = build_context_agent_payload(
            PlannerRequest(
                instruction="Aldera用火球术攻击goblin",
            )
        )

        self.assertEqual("Aldera用火球术攻击goblin", payload["intent"])
        self.assertIn("为后续 resolution 收集", payload["goal"])
        self.assertGreaterEqual(len(payload["requests"]), 3)
        self.assertTrue(all(isinstance(item, str) and item.strip() for item in payload["requests"]))
        self.assertTrue(any("执行者对应哪个实体" in item for item in payload["requests"]))
        self.assertTrue(any("目标对应哪个实体" in item for item in payload["requests"]))
        self.assertTrue(any("规则证据" in item for item in payload["requests"]))
        self.assertTrue(any("爆点或目标位置" in item for item in payload["requests"]))
        self.assertFalse(any(item.endswith("？") for item in payload["requests"]))
        self.assertFalse(any(item in {"caster_id", "target_id", "spell_rule"} for item in payload["requests"]))

    def test_run_context_agent_eval_returns_realtime_bundle_for_default_fixture(self) -> None:
        result = run_context_agent_eval(
            intent="Aldera用火球术攻击goblin",
            dependencies=build_scripted_context_agent_dependencies(search_tool=create_search_stub_tool()),
        )

        self.assertEqual(DEFAULT_CONTEXT_AGENT_EVAL_STATE_FILE.resolve(), result.state_file)
        self.assertEqual("Aldera用火球术攻击goblin", result.payload["intent"])
        self.assertIn("goal", result.payload)
        self.assertIn("requests", result.payload)
        self.assertEqual("needs_human", result.bundle.status)
        self.assertEqual("area_spell", result.bundle.action)
        self.assertIn("actor_id", result.bundle.resolved_entities)
        self.assertFalse(result.bundle.state_evidence)
        self.assertTrue(result.bundle.ask_requests)
        self.assertIsNotNone(result.bundle.pending_interrupt)
        self.assertEqual("pending", result.ask_interaction)
        self.assertTrue(any(note.startswith("goal=") for note in result.bundle.notes))
        self.assertTrue(any(note.startswith("requests=") for note in result.bundle.notes))

    def test_render_context_agent_eval_human_output_contains_key_sections(self) -> None:
        result = run_context_agent_eval(
            intent="Aldera用长剑攻击goblin_1",
            dependencies=build_scripted_context_agent_dependencies(search_tool=create_search_stub_tool()),
        )

        rendered = render_context_agent_eval(result)

        self.assertIn("Context Agent Eval", rendered)
        self.assertIn("Delegated Payload", rendered)
        self.assertIn("Realtime Bundle", rendered)
        self.assertIn("intent: Aldera用长剑攻击goblin_1", rendered)
        self.assertIn("goal:", rendered)
        self.assertIn("requests (", rendered)
        self.assertIn("status: ready", rendered)
        self.assertIn("normalized_instruction:", rendered)
        self.assertIn("resolved_entities:", rendered)
        self.assertIn("rule_evidence", rendered)
        self.assertIn("state_evidence", rendered)
        self.assertIn("citations", rendered)
        self.assertIn("ask_requests", rendered)
        self.assertIn("ask_interaction:", rendered)
        self.assertIn("agent_trace", rendered)
        self.assertIn("notes", rendered)

    def test_render_context_agent_eval_json_output_includes_payload_and_bundle(self) -> None:
        result = run_context_agent_eval(
            intent="Aldera用长剑攻击goblin_1",
            dependencies=build_scripted_context_agent_dependencies(search_tool=create_search_stub_tool()),
        )

        rendered = render_context_agent_eval(result, output_format="json")
        payload = json.loads(rendered)

        self.assertEqual("Aldera用长剑攻击goblin_1", payload["payload"]["intent"])
        self.assertTrue(payload["payload"]["requests"])
        self.assertEqual("ready", payload["bundle"]["status"])
        self.assertIn("state_file", payload)
        self.assertIn("ask_interaction", payload)
        self.assertIn("interrupt_requests", payload)
        self.assertIn("ask_requests", payload["bundle"])

    def test_run_context_agent_eval_allows_state_file_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "state.toml"
            state_path.write_text(
                """
[actors.aldera]
id = "aldera"
name = "Aldera"

[actors.aldera.position]
x = 1
y = 2
""".strip()
                + "\n",
                encoding="utf-8",
            )

            result = run_context_agent_eval(
                intent="Aldera用长剑攻击goblin_1",
                state_file=state_path,
                dependencies=build_scripted_context_agent_dependencies(search_tool=create_search_stub_tool()),
            )

        self.assertEqual(state_path.resolve(), result.state_file)
        self.assertEqual("ready", result.bundle.status)
        self.assertEqual("weapon_attack", result.bundle.action)

    def test_default_intent_constant_matches_cli_default_shape(self) -> None:
        self.assertEqual("Aldera用火球术攻击goblin_1", DEFAULT_CONTEXT_AGENT_EVAL_INTENT)

    def test_prompt_for_ask_requests_accepts_default_and_custom_input(self) -> None:
        requests = [
            AskRequest(
                question_id="target",
                prompt="请选择目标",
                options=[
                    {"id": "goblin_1", "label": "goblin_1"},
                    {"id": "goblin_2", "label": "goblin_2"},
                ],
                default_option_id="goblin_1",
                allow_custom_input=True,
                custom_input_label="输入自定义目标",
            ),
            AskRequest(
                question_id="point",
                prompt="请输入爆点",
                allow_custom_input=True,
                custom_input_label="爆点",
            ),
        ]

        answers = iter(["", "custom:(8,9)"])
        responses = prompt_for_ask_requests(requests, input_func=lambda _prompt: next(answers))

        self.assertEqual("goblin_1", responses[0].selected_option_id)
        self.assertEqual("(8,9)", responses[1].custom_input)

    def test_maybe_collect_cli_ask_responses_records_answers(self) -> None:
        result = run_context_agent_eval(
            intent="Aldera用火球术攻击goblin",
            dependencies=build_scripted_context_agent_dependencies(search_tool=create_search_stub_tool()),
        )

        with patch("augury.agent.utils.context_eval.prompt_for_ask_requests") as mocked_prompt:
            mocked_prompt.return_value = [
                {"question_id": "target_disambiguation", "selected_option_id": "goblin_1"},
                {"question_id": "area_point", "custom_input": "(5,10)"},
            ]
            updated = maybe_collect_cli_ask_responses(result)

        self.assertIsNotNone(updated.ask_responses)
        self.assertEqual(2, len(updated.ask_responses))
        self.assertEqual("collected", updated.ask_interaction)
        self.assertIn("Collected DM answers", updated.ask_interaction_message or "")

    def test_run_context_agent_eval_sync_ask_resumes_and_returns_final_bundle(self) -> None:
        answers = iter(["goblin_1", ""])
        with patch("augury.agent.utils.context_eval.prompt_for_ask_requests") as mocked_prompt:
            mocked_prompt.side_effect = lambda requests: [prompt_for_ask_requests(requests, input_func=lambda _prompt: next(answers))[0]]
            result = run_context_agent_eval(
                intent="Aldera用火球术攻击goblin",
                dependencies=build_scripted_context_agent_dependencies(search_tool=create_search_stub_tool()),
                sync_ask=True,
            )

        self.assertEqual("ready", result.bundle.status)
        self.assertEqual("resumed", result.ask_interaction)
        self.assertEqual(2, len(result.interrupt_requests or []))
        self.assertEqual(2, len(result.ask_responses or []))
        self.assertFalse(result.bundle.ask_requests)
        self.assertIsNone(result.bundle.pending_interrupt)
        self.assertTrue(result.bundle.state_evidence)

    def test_mark_cli_ask_interaction_skipped_records_reason(self) -> None:
        result = run_context_agent_eval(
            intent="Aldera用火球术攻击goblin",
            dependencies=build_scripted_context_agent_dependencies(search_tool=create_search_stub_tool()),
        )

        updated = mark_cli_ask_interaction_skipped(
            result,
            reason="Ask interaction was skipped because stdin is not an interactive TTY.",
        )

        self.assertEqual("skipped", updated.ask_interaction)
        self.assertIn("not an interactive TTY", updated.ask_interaction_message or "")

    def test_render_context_agent_eval_mentions_resume_result_after_sync_ask(self) -> None:
        answers = iter(["goblin_1", ""])
        with patch("augury.agent.utils.context_eval.prompt_for_ask_requests") as mocked_prompt:
            mocked_prompt.side_effect = lambda requests: [prompt_for_ask_requests(requests, input_func=lambda _prompt: next(answers))[0]]
            result = run_context_agent_eval(
                intent="Aldera用火球术攻击goblin",
                dependencies=build_scripted_context_agent_dependencies(search_tool=create_search_stub_tool()),
                sync_ask=True,
            )

        rendered = render_context_agent_eval(result)

        self.assertIn("resume_result: Context Agent resumed after ask", rendered)

    def test_render_context_agent_eval_json_reports_skipped_interaction(self) -> None:
        result = run_context_agent_eval(
            intent="Aldera用火球术攻击goblin",
            dependencies=build_scripted_context_agent_dependencies(search_tool=create_search_stub_tool()),
        )
        result = mark_cli_ask_interaction_skipped(
            result,
            reason="Ask interaction was skipped because --json was requested.",
        )

        rendered = render_context_agent_eval(result, output_format="json")
        payload = json.loads(rendered)

        self.assertEqual("skipped", payload["ask_interaction"])
        self.assertIn("--json", payload["ask_interaction_message"])

    def test_runtime_loads_context_agent_prompt_templates_from_config(self) -> None:
        captured: dict[str, object] = {}

        def factory(**kwargs: object) -> object:
            captured["system_prompt"] = kwargs.get("system_prompt")

            class Agent:
                def invoke(self, payload: dict[str, object]) -> dict[str, object]:
                    captured["user_prompt"] = payload["messages"][0]["content"]  # type: ignore[index]
                    return {
                        "structured_response": {
                            "status": "ready",
                            "action": "weapon_attack",
                            "resolved_entities": {"actor_id": "aldera", "target_id": "goblin_1"},
                            "derived_context": {},
                            "notes": ["action=weapon_attack"],
                        }
                    }

            return Agent()

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(
                Path(temp_dir) / "config.toml",
                planner_context_agent_system_prompt_template="Context agent system prompt from config",
                planner_context_agent_user_prompt_template=DEFAULT_CONTEXT_AGENT_TEST_USER_PROMPT,
            )
            with patch.dict("os.environ", {"PLANNER_API_KEY": "test-key", "SEARCH_API_KEY": "search-key"}, clear=False):
                result = run_context_agent_eval(
                    intent="Aldera用长剑攻击goblin_1",
                    config_path=config_path,
                    dependencies=PlannerDependencies(
                        search_tool=create_search_stub_tool(),
                        context_agent_agent_factory=factory,
                    ),
                )

        self.assertEqual("ready", result.bundle.status)
        self.assertEqual("Context agent system prompt from config", captured["system_prompt"])
        self.assertIn("Intent: Aldera用长剑攻击goblin_1", str(captured["user_prompt"]))
        self.assertIn("Current state evidence:", str(captured["user_prompt"]))


class MainAgentContextSkillPromptTests(unittest.TestCase):
    def test_main_agent_prompt_teaches_intent_goal_requests_contract(self) -> None:
        prompt = Path("config/prompts/planner_system.txt").read_text(encoding="utf-8")

        self.assertIn("intent", prompt)
        self.assertIn("goal", prompt)
        self.assertIn("requests", prompt)
        self.assertIn("自然语言事实获取请求", prompt)

    def test_context_agent_prompt_examples_avoid_field_names_and_questions(self) -> None:
        prompt = Path("config/prompts/planner_context_agent_user.txt").read_text(encoding="utf-8")

        self.assertIn("Intent:", prompt)
        self.assertIn("Goal:", prompt)
        self.assertIn("Requests:", prompt)
        self.assertIn("不要把 requests 写成字段名列表", prompt)
        self.assertIn("不要把 requests 写成问句列表", prompt)
        self.assertIn("是否发起 ask 必须由你的推理决定", prompt)
        self.assertIn("只有在缺口已经阻止你安全落地时，才发起 ask", prompt)


if __name__ == "__main__":
    unittest.main()
