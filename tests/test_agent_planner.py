from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain.agents.structured_output import StructuredOutputValidationError, ToolStrategy
from langchain_core.messages import AIMessage
from langgraph.types import Interrupt

from tests.config_helpers import write_project_config
from trpg_py.agent import PlannerRequest, create_planner, resolve_planner_factory_config
from trpg_py.config import DEFAULT_PROJECT_CONFIG_PATH, clear_project_config_cache


class DummyTool:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeDeepAgent:
    def __init__(
        self,
        *,
        responses: list[object] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.responses = list(responses or [])
        self.error = error
        self.calls: list[dict[str, object]] = []

    def invoke(self, payload: object, config: dict[str, object] | None = None) -> object:
        self.calls.append({"input": payload, "config": config})
        if self.error is not None:
            raise self.error
        if not self.responses:
            raise AssertionError("No fake responses remaining")
        return self.responses.pop(0)


class FakeAgentFactory:
    def __init__(
        self,
        *,
        responses: list[object] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.responses = responses or []
        self.error = error
        self.calls: list[dict[str, object]] = []
        self.agent: FakeDeepAgent | None = None

    def __call__(self, **kwargs: object) -> FakeDeepAgent:
        self.calls.append(kwargs)
        self.agent = FakeDeepAgent(responses=self.responses, error=self.error)
        return self.agent


class ToolCallingAgentFactory:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.agent: FakeDeepAgent | None = None

    def __call__(self, **kwargs: object) -> FakeDeepAgent:
        self.calls.append(kwargs)
        tools = {tool.name: tool for tool in kwargs["tools"]}

        class _Agent:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def invoke(self, payload: object, config: dict[str, object] | None = None) -> object:
                self.calls.append({"input": payload, "config": config})
                tools["fetch_keys"].invoke({"prefix": "actors"})
                return {
                    "structured_response": {
                        "status": "needs_human",
                        "questions": [{"question": "Which goblin?"}],
                        "missing_info": ["target_id"],
                    }
                }

        self.agent = _Agent()
        return self.agent


class PlannerFactoryConfigTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_project_config_cache()

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_explicit_factory_args_override_project_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")

            config = resolve_planner_factory_config(
                model="openai:explicit-model",
                base_url="https://explicit.example/v1",
                api_key="explicit-key",
                timeout=45.0,
                max_retries=9,
                interrupt_on={"human": True},
                max_planning_rounds=3,
                tool_budget=8,
                config_path=str(config_path),
            )

        self.assertEqual("openai:explicit-model", config.model)
        self.assertEqual("https://explicit.example/v1", config.base_url)
        self.assertEqual("explicit-key", config.api_key)
        self.assertEqual(45.0, config.timeout)
        self.assertEqual(9, config.max_retries)
        self.assertEqual({"human": True}, config.interrupt_on)
        self.assertEqual(3, config.max_planning_rounds)
        self.assertEqual(8, config.tool_budget)

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_factory_uses_project_config_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")

            config = resolve_planner_factory_config(config_path=str(config_path))

        self.assertEqual("openai:test-planner", config.model)
        self.assertEqual("https://planner.example/v1", config.base_url)
        self.assertEqual("planner-key", config.api_key)
        self.assertEqual(42.0, config.timeout)
        self.assertEqual(5, config.max_retries)
        self.assertEqual({"human": True}, config.interrupt_on)
        self.assertEqual(3, config.max_planning_rounds)
        self.assertEqual(7, config.tool_budget)
        self.assertEqual("System prompt budget {{tool_budget}}", config.system_prompt_template)
        self.assertIn("{{instruction}}", config.user_prompt_template)

    def test_explicit_factory_args_do_not_require_loading_project_config(self) -> None:
        config = resolve_planner_factory_config(
            model="openai:explicit-only",
            base_url="https://explicit.example/v1",
            api_key="explicit-key",
            timeout=12.0,
            max_retries=2,
            interrupt_on={},
            max_planning_rounds=1,
            tool_budget=2,
            system_prompt_template="System prompt budget {{tool_budget}}",
            user_prompt_template="Instruction: {{instruction}}",
            config_path="/tmp/definitely-missing-config.toml",
        )

        self.assertEqual("openai:explicit-only", config.model)
        self.assertEqual(2, config.tool_budget)


class PlannerTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_project_config_cache()

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_factory_passes_tools_and_checkpointer_to_deep_agent(self) -> None:
        captured_config: list[object] = []
        agent_factory = FakeAgentFactory(
            responses=[
                {
                    "structured_response": {
                        "status": "needs_human",
                        "questions": [{"question": "Which goblin?"}],
                    }
                }
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")

            def fake_model_builder(config: object) -> str:
                captured_config.append(config)
                return "fake-model"

            planner = create_planner(
                model="openai:test-model",
                base_url="https://gateway.example/v1",
                api_key="secret",
                timeout=33.0,
                max_retries=7,
                interrupt_on={"human": True},
                config_path=str(config_path),
                search_tool=DummyTool("search"),
                fetch_keys_tool=DummyTool("fetch_keys"),
                model_builder=fake_model_builder,
                agent_factory=agent_factory,
            )

            result = planner.plan(PlannerRequest(instruction="Goblin attacks hero_1"))

        self.assertEqual("needs_human", result.status)
        self.assertEqual("fake-model", agent_factory.calls[0]["model"])
        self.assertEqual("System prompt budget 7", agent_factory.calls[0]["system_prompt"])
        self.assertEqual({"human": True}, agent_factory.calls[0]["interrupt_on"])
        self.assertIsNotNone(agent_factory.calls[0]["checkpointer"])
        self.assertIsInstance(agent_factory.calls[0]["response_format"], ToolStrategy)
        self.assertEqual(["PlannerResult"], [spec.name for spec in agent_factory.calls[0]["response_format"].schema_specs])
        self.assertEqual(["search", "fetch_keys", "reads", "lint"], [tool.name for tool in agent_factory.calls[0]["tools"]])
        self.assertEqual("openai:test-model", captured_config[0].model)

    @patch.dict(
        os.environ,
        {"LINGYA_API_KEY": "planner-key", "SILICONFLOW_API_KEY": "search-key"},
        clear=False,
    )
    def test_default_prompt_templates_include_dsl_guidance_and_lint_strategy(self) -> None:
        agent_factory = FakeAgentFactory(
            responses=[
                {
                    "structured_response": {
                        "status": "needs_human",
                        "questions": [{"question": "Need more target detail"}],
                    }
                }
            ]
        )
        planner = create_planner(
            config_path=str(DEFAULT_PROJECT_CONFIG_PATH),
            search_tool=DummyTool("search"),
            fetch_keys_tool=DummyTool("fetch_keys"),
            reads_tool=DummyTool("reads"),
            lint_tool=DummyTool("lint"),
            model_builder=lambda config: "fake-model",
            agent_factory=agent_factory,
        )

        planner.plan({"instruction": "Goblin attacks hero_1"})

        system_prompt = agent_factory.calls[0]["system_prompt"]
        user_prompt = agent_factory.agent.calls[0]["input"]["messages"][0]["content"]
        self.assertIn("use lint to validate your candidate TaskDocument", system_prompt)
        self.assertIn("Use reads when you know or can discover promising state paths", system_prompt)
        self.assertIn("For `fetch_keys` and reads, use bare store paths like actors.aldera.ac.", system_prompt)
        self.assertIn("Reserve state., context., and result. namespaces for TaskDocument $ref values only.", system_prompt)
        self.assertIn("TaskDocument minimal shape", user_prompt)
        self.assertIn("Use reads to confirm the current values", user_prompt)
        self.assertIn("Allowed type/kind pairs", user_prompt)
        self.assertIn("Do not invent substitute step fields", user_prompt)
        self.assertIn("Canonical example", user_prompt)
        self.assertIn("Use lint to validate a candidate TaskDocument", user_prompt)
        self.assertIn("fetch_keys and reads use bare store paths such as actors.goblin_1.ac", user_prompt)
        self.assertIn("Do not pass state.actors.goblin_1.ac directly to fetch_keys or reads.", user_prompt)
        self.assertIn("tool path actors.goblin_1.ac -> TaskDocument $ref state.actors.goblin_1.ac", user_prompt)
        self.assertIn('reads paths: ["actors.goblin_1.attacks.scimitar.to_hit", "actors.aldera.ac"]', user_prompt)
        self.assertIn("Do not pass state.* references directly into `fetch_keys` or `reads`.", user_prompt)
        self.assertIn("convert a confirmed tool path like actors.aldera.ac into the $ref form state.actors.aldera.ac", user_prompt)
        self.assertIn('tags=["nat"]', system_prompt)
        self.assertIn('tags=["nat"]', user_prompt)
        self.assertIn("Do not treat a natural 20 attack as an ordinary success", user_prompt)
        self.assertIn("result.attack_roll.outcome == crit_success", user_prompt)
        self.assertIn("damage.apply.is_critical", user_prompt)

    @patch.dict(
        os.environ,
        {"LINGYA_API_KEY": "planner-key", "SILICONFLOW_API_KEY": "search-key"},
        clear=False,
    )
    def test_default_prompt_templates_do_not_use_state_namespace_as_tool_examples(self) -> None:
        agent_factory = FakeAgentFactory(
            responses=[
                {
                    "structured_response": {
                        "status": "needs_human",
                        "questions": [{"question": "Need more target detail"}],
                    }
                }
            ]
        )
        planner = create_planner(
            config_path=str(DEFAULT_PROJECT_CONFIG_PATH),
            search_tool=DummyTool("search"),
            fetch_keys_tool=DummyTool("fetch_keys"),
            reads_tool=DummyTool("reads"),
            lint_tool=DummyTool("lint"),
            model_builder=lambda config: "fake-model",
            agent_factory=agent_factory,
        )

        planner.plan({"instruction": "Goblin attacks hero_1"})

        user_prompt = agent_factory.agent.calls[0]["input"]["messages"][0]["content"]
        self.assertNotIn("fetch_keys prefix: state.actors", user_prompt)
        self.assertNotIn('reads paths: ["state.actors.goblin_1.attacks.scimitar.to_hit"', user_prompt)
        self.assertNotIn("Use fetch_keys to discover candidate state.actors paths", user_prompt)

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_factory_builds_default_reads_tool_from_state(self) -> None:
        agent_factory = FakeAgentFactory(
            responses=[
                {
                    "structured_response": {
                        "status": "needs_human",
                        "questions": [{"question": "Need more target detail"}],
                    }
                }
            ]
        )
        state = {"actors": {"aldera": {"id": "aldera", "ac": 18}}}
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")
            planner = create_planner(
                config_path=str(config_path),
                state=state,
                search_tool=DummyTool("search"),
                fetch_keys_tool=DummyTool("fetch_keys"),
                model_builder=lambda config: "fake-model",
                agent_factory=agent_factory,
            )

        output = planner.reads_tool.invoke({"paths": ["actors.aldera.id", "actors.aldera.ac"]})
        self.assertEqual("ok", output["status"])
        self.assertEqual("aldera", output["items"][0]["value"])
        self.assertEqual(18, output["items"][1]["value"])

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_factory_builds_default_search_tool_from_project_config(self) -> None:
        agent_factory = FakeAgentFactory(
            responses=[
                {
                    "structured_response": {
                        "status": "needs_human",
                        "questions": [{"question": "Need more target detail"}],
                    }
                }
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")
            planner = create_planner(
                config_path=str(config_path),
                fetch_keys_tool=DummyTool("fetch_keys"),
                model_builder=lambda config: "fake-model",
                agent_factory=agent_factory,
            )

        self.assertEqual("rules", planner.search_tool.searcher.collection_name)
        self.assertEqual("http://qdrant.example:6333", planner.search_tool.searcher.qdrant_url)
        self.assertEqual(4, planner.search_tool.searcher.default_limit)
        self.assertEqual(11, planner.search_tool.searcher.default_fetch_k)

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_plan_returns_ready_for_valid_task_document(self) -> None:
        valid_document = {
            "task_id": "goblin_scimitar_attack",
            "version": 1,
            "policy": {"ruleset": "dnd5e-2014"},
            "context": {"target_id": "hero_1"},
            "steps": [
                {
                    "id": "attack_roll",
                    "type": "check",
                    "kind": "attack",
                    "tags": ["nat"],
                    "args": {
                        "dice": "1d20",
                        "modifier": 4,
                        "target_id": {"$ref": "context.target_id"},
                        "target_ac": 15,
                    },
                }
            ],
        }
        agent_factory = FakeAgentFactory(
            responses=[
                {
                    "structured_response": {
                        "status": "ready",
                        "task_document": valid_document,
                        "assumptions": [],
                        "missing_info": [],
                    }
                }
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")
            planner = create_planner(
                config_path=str(config_path),
                search_tool=DummyTool("search"),
                fetch_keys_tool=DummyTool("fetch_keys"),
                model_builder=lambda config: "fake-model",
                agent_factory=agent_factory,
            )

            result = planner.plan({"instruction": "Goblin attacks hero_1"})

        self.assertEqual("ready", result.status)
        self.assertEqual("goblin_scimitar_attack", result.task_document["task_id"])
        self.assertEqual(1, len(agent_factory.agent.calls))
        self.assertIn("Instruction: Goblin attacks hero_1", agent_factory.agent.calls[0]["input"]["messages"][0]["content"])
        self.assertIn("Budget: 7", agent_factory.agent.calls[0]["input"]["messages"][0]["content"])

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_plan_includes_debug_attempts_when_requested(self) -> None:
        valid_document = {
            "task_id": "goblin_scimitar_attack",
            "version": 1,
            "policy": {},
            "context": {},
            "steps": [
                {
                    "id": "attack_roll",
                    "type": "check",
                    "kind": "attack",
                    "args": {"dice": "1d20", "modifier": 4, "target_id": "hero_1", "target_ac": 16},
                }
            ],
        }
        agent_factory = FakeAgentFactory(
            responses=[
                {
                    "structured_response": {
                        "status": "ready",
                        "task_document": valid_document,
                    }
                }
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")
            planner = create_planner(
                config_path=str(config_path),
                search_tool=DummyTool("search"),
                fetch_keys_tool=DummyTool("fetch_keys"),
                model_builder=lambda config: "fake-model",
                agent_factory=agent_factory,
            )

            result = planner.plan({"instruction": "Goblin attacks hero_1", "debug": True})

        self.assertEqual("ready", result.status)
        self.assertIsNotNone(result.debug)
        self.assertEqual(1, len(result.debug.attempts))
        self.assertEqual(1, result.debug.attempts[0].round)
        self.assertEqual("prompt", result.debug.attempts[0].input_mode)
        self.assertIsNone(result.debug.failure_stage)

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_plan_repairs_invalid_ready_output(self) -> None:
        invalid_document = {
            "task_id": "broken",
            "version": 1,
            "steps": [{"id": "step_1", "type": "check", "args": {}}],
        }
        valid_document = {
            "task_id": "fixed",
            "version": 1,
            "policy": {},
            "context": {},
            "steps": [
                {
                    "id": "attack_roll",
                    "type": "check",
                    "kind": "attack",
                    "args": {"dice": "1d20", "modifier": 3, "target_id": "hero_1", "target_ac": 14},
                }
            ],
        }
        agent_factory = FakeAgentFactory(
            responses=[
                {"structured_response": {"status": "ready", "task_document": invalid_document}},
                {"structured_response": {"status": "ready", "task_document": valid_document}},
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")
            planner = create_planner(
                config_path=str(config_path),
                search_tool=DummyTool("search"),
                fetch_keys_tool=DummyTool("fetch_keys"),
                model_builder=lambda config: "fake-model",
                agent_factory=agent_factory,
            )

            result = planner.plan({"instruction": "Fix the previous plan"})

        self.assertEqual("ready", result.status)
        self.assertEqual("fixed", result.task_document["task_id"])
        self.assertEqual(2, len(agent_factory.agent.calls))
        self.assertIn("Repair:", agent_factory.agent.calls[1]["input"]["messages"][0]["content"])

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_plan_returns_blocked_when_agent_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")
            planner = create_planner(
                config_path=str(config_path),
                search_tool=DummyTool("search"),
                fetch_keys_tool=DummyTool("fetch_keys"),
                model_builder=lambda config: "fake-model",
                agent_factory=FakeAgentFactory(error=RuntimeError("llm unavailable")),
            )

            result = planner.plan({"instruction": "Attack the goblin"})

        self.assertEqual("blocked", result.status)
        self.assertEqual("RuntimeError", result.error.type)
        self.assertIn("llm unavailable", result.error.message)

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_plan_falls_back_to_needs_human_after_repair_budget_exhausted(self) -> None:
        invalid_document = {
            "task_id": "still-broken",
            "version": 1,
            "steps": [{"id": "step_1", "type": "check", "args": {}}],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")
            planner = create_planner(
                config_path=str(config_path),
                max_planning_rounds=1,
                search_tool=DummyTool("search"),
                fetch_keys_tool=DummyTool("fetch_keys"),
                model_builder=lambda config: "fake-model",
                agent_factory=FakeAgentFactory(
                    responses=[{"structured_response": {"status": "ready", "task_document": invalid_document}}]
                ),
            )

            result = planner.plan({"instruction": "Attack something"})

        self.assertEqual("needs_human", result.status)
        self.assertEqual(["task_document_validation"], result.missing_info)
        self.assertIn("TaskDocument", result.questions[0].question)

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_plan_exposes_validation_failure_in_debug_payload(self) -> None:
        invalid_document = {
            "task_id": "still-broken",
            "version": 1,
            "steps": [{"id": "step_1", "type": "check", "args": {}}],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")
            planner = create_planner(
                config_path=str(config_path),
                max_planning_rounds=1,
                search_tool=DummyTool("search"),
                fetch_keys_tool=DummyTool("fetch_keys"),
                model_builder=lambda config: "fake-model",
                agent_factory=FakeAgentFactory(
                    responses=[{"structured_response": {"status": "ready", "task_document": invalid_document}}]
                ),
            )

            result = planner.plan({"instruction": "Attack something", "debug": True})

        self.assertEqual("needs_human", result.status)
        self.assertEqual("task_document_validation", result.reason)
        self.assertIsNotNone(result.debug)
        self.assertEqual("schema_or_semantic_validation", result.debug.failure_stage)
        self.assertIn("Field required", result.debug.failure_message)
        self.assertEqual(1, len(result.debug.attempts))
        self.assertIn("Field required", result.debug.attempts[0].validation_error)

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_plan_treats_non_string_damage_dice_as_repairable_validation_failure(self) -> None:
        invalid_document = {
            "task_id": "broken_damage",
            "version": 1,
            "steps": [
                {
                    "id": "attack_roll",
                    "type": "check",
                    "kind": "attack",
                    "args": {"dice": "1d20", "modifier": 4, "target_id": "hero_1", "target_ac": 16},
                    "tags": ["nat"],
                },
                {
                    "id": "apply_damage",
                    "type": "damage",
                    "kind": "apply",
                    "args": {
                        "targets": ["hero_1"],
                        "damage": [{"dice": {"count": 1, "sides": 6}, "bonus": 2, "damage_type": "slashing"}],
                    },
                },
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")
            planner = create_planner(
                config_path=str(config_path),
                max_planning_rounds=1,
                search_tool=DummyTool("search"),
                fetch_keys_tool=DummyTool("fetch_keys"),
                model_builder=lambda config: "fake-model",
                agent_factory=FakeAgentFactory(
                    responses=[{"structured_response": {"status": "ready", "task_document": invalid_document}}]
                ),
            )

            result = planner.plan({"instruction": "Attack something", "debug": True})

        self.assertEqual("needs_human", result.status)
        self.assertEqual("task_document_validation", result.reason)
        self.assertIsNotNone(result.debug)
        self.assertEqual("schema_or_semantic_validation", result.debug.failure_stage)
        self.assertIn("damage component dice must be a dice string", result.debug.failure_message)
        self.assertEqual(1, len(result.debug.attempts))
        self.assertIn("damage component dice must be a dice string", result.debug.attempts[0].validation_error)

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_plan_exposes_agent_error_in_debug_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")
            planner = create_planner(
                config_path=str(config_path),
                search_tool=DummyTool("search"),
                fetch_keys_tool=DummyTool("fetch_keys"),
                model_builder=lambda config: "fake-model",
                agent_factory=FakeAgentFactory(error=RuntimeError("llm unavailable")),
            )

            result = planner.plan({"instruction": "Attack the goblin", "debug": True})

        self.assertEqual("blocked", result.status)
        self.assertEqual("agent_error", result.reason)
        self.assertIsNotNone(result.debug)
        self.assertEqual("agent_error", result.debug.failure_stage)
        self.assertEqual("llm unavailable", result.debug.failure_message)

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_plan_writes_run_log_file_for_successful_run(self) -> None:
        valid_document = {
            "task_id": "goblin_scimitar_attack",
            "version": 1,
            "policy": {},
            "context": {},
            "steps": [
                {
                    "id": "attack_roll",
                    "type": "check",
                    "kind": "attack",
                    "args": {"dice": "1d20", "modifier": 4, "target_id": "hero_1", "target_ac": 16},
                }
            ],
        }
        agent_factory = FakeAgentFactory(
            responses=[
                {
                    "structured_response": {
                        "status": "ready",
                        "task_document": valid_document,
                    }
                }
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")
            planner = create_planner(
                config_path=str(config_path),
                search_tool=DummyTool("search"),
                fetch_keys_tool=DummyTool("fetch_keys"),
                model_builder=lambda config: "fake-model",
                agent_factory=agent_factory,
            )

            result = planner.plan({"instruction": "Attack the goblin"})

            self.assertEqual("ready", result.status)
            self.assertIsNotNone(planner.last_run_log_path)
            log_path = Path(planner.last_run_log_path)
            self.assertTrue(log_path.exists())
            self.assertIn(str(Path(temp_dir) / "logs" / "planner"), str(log_path))
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("planner run started", log_text)
            self.assertIn("planner round started", log_text)
            self.assertIn("planner run finished", log_text)

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_plan_logs_structured_output_validation_error_details(self) -> None:
        structured_error = StructuredOutputValidationError(
            "PlannerResult",
            ValueError("Extra data: line 2 column 1"),
            AIMessage(content='{"status":"ready"}\nextra output'),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")
            planner = create_planner(
                config_path=str(config_path),
                search_tool=DummyTool("search"),
                fetch_keys_tool=DummyTool("fetch_keys"),
                model_builder=lambda config: "fake-model",
                agent_factory=FakeAgentFactory(error=structured_error),
            )

            result = planner.plan({"instruction": "Cast fireball", "debug": True})

            self.assertEqual("blocked", result.status)
            self.assertEqual("agent_error", result.reason)
            self.assertIsNotNone(planner.last_run_log_path)
            log_path = Path(planner.last_run_log_path)
            self.assertTrue(log_path.exists())
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("StructuredOutputValidationError", log_text)
            self.assertIn("PlannerResult", log_text)
            self.assertIn("Extra data: line 2 column 1", log_text)
            self.assertIn("extra output", log_text)

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_plan_log_file_correlates_tool_logs_with_round_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")
            agent_factory = ToolCallingAgentFactory()
            planner = create_planner(
                config_path=str(config_path),
                state={"actors": {"aldera": {"ac": 18}, "goblin_1": {"hp": {"current": 7}}}},
                search_tool=DummyTool("search"),
                model_builder=lambda config: "fake-model",
                agent_factory=agent_factory,
            )

            result = planner.plan({"instruction": "Inspect current actors"})

            self.assertEqual("needs_human", result.status)
            self.assertIsNotNone(planner.last_run_log_path)
            log_text = Path(planner.last_run_log_path).read_text(encoding="utf-8")
            self.assertIn("tool_input tool=fetch_keys prefix='actors'", log_text)
            self.assertIn('"planner_round": "1"', log_text)

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_plan_returns_needs_human_with_resume_token_when_hitl_interrupts(self) -> None:
        interrupt_payload = {
            "action_requests": [
                {
                    "name": "search",
                    "args": {"query": "scimitar attack"},
                    "description": "Approve the search tool call before continuing.",
                }
            ],
            "review_configs": [
                {
                    "action_name": "search",
                    "allowed_decisions": ["approve", "edit", "reject"],
                }
            ],
        }
        agent_factory = FakeAgentFactory(
            responses=[
                {
                    "__interrupt__": [Interrupt(value=interrupt_payload, id="interrupt-1")],
                }
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")
            planner = create_planner(
                config_path=str(config_path),
                search_tool=DummyTool("search"),
                fetch_keys_tool=DummyTool("fetch_keys"),
                model_builder=lambda config: "fake-model",
                agent_factory=agent_factory,
            )

            result = planner.plan({"instruction": "Goblin attacks hero_1"})

        self.assertEqual("needs_human", result.status)
        self.assertEqual(["human_review"], result.missing_info)
        self.assertIsNotNone(result.resume)
        self.assertTrue(result.resume.thread_id)
        self.assertEqual(
            "Approve the search tool call before continuing.",
            result.questions[0].question,
        )
        self.assertEqual(["approve", "edit", "reject"], result.questions[0].options)
        self.assertEqual(
            result.resume.thread_id,
            agent_factory.agent.calls[0]["config"]["configurable"]["thread_id"],
        )

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_plan_can_resume_after_hitl_interrupt(self) -> None:
        interrupt_payload = {
            "action_requests": [
                {
                    "name": "search",
                    "args": {"query": "scimitar attack"},
                    "description": "Approve the search tool call before continuing.",
                }
            ],
            "review_configs": [
                {
                    "action_name": "search",
                    "allowed_decisions": ["approve", "edit", "reject"],
                }
            ],
        }
        valid_document = {
            "task_id": "goblin_scimitar_attack",
            "version": 1,
            "policy": {},
            "context": {},
            "steps": [
                {
                    "id": "attack_roll",
                    "type": "check",
                    "kind": "attack",
                    "args": {"dice": "1d20", "modifier": 4, "target_id": "hero_1", "target_ac": 16},
                }
            ],
        }
        agent_factory = FakeAgentFactory(
            responses=[
                {
                    "__interrupt__": [Interrupt(value=interrupt_payload, id="interrupt-1")],
                },
                {
                    "structured_response": {
                        "status": "ready",
                        "task_document": valid_document,
                    }
                },
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")
            planner = create_planner(
                config_path=str(config_path),
                search_tool=DummyTool("search"),
                fetch_keys_tool=DummyTool("fetch_keys"),
                model_builder=lambda config: "fake-model",
                agent_factory=agent_factory,
            )

            interrupted = planner.plan({"instruction": "Goblin attacks hero_1"})
            resumed = planner.plan(
                {
                    "instruction": "Goblin attacks hero_1",
                    "thread_id": interrupted.resume.thread_id,
                    "resume": {"decisions": [{"type": "approve"}]},
                }
            )

        self.assertEqual("needs_human", interrupted.status)
        self.assertEqual("human_review", interrupted.reason)
        self.assertEqual("ready", resumed.status)
        self.assertEqual("goblin_scimitar_attack", resumed.task_document["task_id"])
        self.assertEqual(
            interrupted.resume.thread_id,
            agent_factory.agent.calls[1]["config"]["configurable"]["thread_id"],
        )
        self.assertEqual(
            {"decisions": [{"type": "approve"}]},
            agent_factory.agent.calls[1]["input"].resume,
        )

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_create_planner_fails_when_prompt_template_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(
                Path(temp_dir) / "config.toml",
                planner_prompt_user_file="missing_user_prompt.txt",
            )
            (Path(temp_dir) / "prompts" / "missing_user_prompt.txt").unlink()

            with self.assertRaisesRegex(ValueError, "missing_user_prompt.txt"):
                create_planner(
                    config_path=str(config_path),
                    search_tool=DummyTool("search"),
                    fetch_keys_tool=DummyTool("fetch_keys"),
                    model_builder=lambda config: "fake-model",
                    agent_factory=FakeAgentFactory(),
                )

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_create_planner_fails_when_prompt_template_has_unknown_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(
                Path(temp_dir) / "config.toml",
                planner_system_prompt_template="System prompt {{unknown_value}}",
            )

            with self.assertRaisesRegex(ValueError, "unsupported placeholders"):
                create_planner(
                    config_path=str(config_path),
                    search_tool=DummyTool("search"),
                    fetch_keys_tool=DummyTool("fetch_keys"),
                    model_builder=lambda config: "fake-model",
                    agent_factory=FakeAgentFactory(),
                )


if __name__ == "__main__":
    unittest.main()
