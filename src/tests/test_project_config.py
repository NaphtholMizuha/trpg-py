from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from augury.config import (
    PROJECT_LEVEL_CONFIG_SECTIONS,
    ProjectConfigError,
    STATIC_FIXTURE_CATEGORIES,
    clear_project_config_cache,
    is_project_level_config_section,
    load_project_config,
    resolve_path_from_config,
)
from tests.config_helpers import write_project_config


class ProjectConfigTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_project_config_cache()

    @patch.dict(
        os.environ,
        {"PLANNER_API_KEY": "planner-key", "SEARCH_API_KEY": "search-key"},
        clear=False,
    )
    def test_load_project_config_returns_typed_config_and_reuses_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")

            first = load_project_config(config_path)
            second = load_project_config(config_path)

        self.assertIs(first, second)
        self.assertEqual("openai:test-planner", first.planner.model)
        self.assertEqual("planner-key", first.planner.api_key)
        self.assertEqual("prompts", first.planner.main_prompt.directory)
        self.assertEqual("planner_system.txt", first.planner.main_prompt.system_file)
        self.assertEqual("planner_context_agent_system.txt", first.planner.context_agent_prompt.system_file)
        self.assertEqual("planner_context_agent_user.txt", first.planner.context_agent_prompt.user_file)
        self.assertEqual(
            "planner_resolution_agent_system.txt",
            first.planner.resolution_agent_prompt.system_file,
        )
        self.assertEqual(
            "planner_resolution_agent_user.txt",
            first.planner.resolution_agent_prompt.user_file,
        )
        self.assertEqual("world_state.toml", first.planner.evals.world_state_file)
        self.assertEqual("https://search.example/v1", first.search.api.base_url)
        self.assertEqual("search-key", first.search.api.api_key)
        self.assertEqual("rules", first.search.qdrant.collection_name)

    def test_load_project_config_raises_for_missing_file(self) -> None:
        missing_path = Path("/tmp/does-not-exist-config.toml")

        with self.assertRaisesRegex(ProjectConfigError, str(missing_path)):
            load_project_config(missing_path)

    def test_load_project_config_raises_for_invalid_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(
                """[planner]
model = "openai:test"
base_url = "https://planner.example/v1"
api_key_env = "PLANNER_API_KEY"
timeout = 42
max_retries = "oops"
interrupt_on = {}
max_planning_rounds = 2
tool_budget = 4

[planner.main_prompt]
directory = "prompts"
system_file = "planner_system.txt"
user_file = "planner_user.txt"

[planner.context_agent_prompt]
system_file = "planner_context_agent_system.txt"
user_file = "planner_context_agent_user.txt"

[planner.resolution_agent_prompt]
system_file = "planner_resolution_agent_system.txt"
user_file = "planner_resolution_agent_user.txt"

[planner.evals]
world_state_file = "world_state.toml"

[search.api]
base_url = "https://search.example/v1"
api_key_env = "SEARCH_API_KEY"

[search.models]
dense_embedding = "dense"
sparse_embedding = "sparse"
reranker = "reranker"

[search.qdrant]
url = "http://qdrant.example:6333"
collection_name = "rules"
dense_vector_name = "dense"
sparse_vector_name = "sparse"

[search]
default_limit = 4
default_fetch_k = 11
rerank_timeout = 17.0
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectConfigError, "max_retries"):
                load_project_config(config_path)

    def test_load_project_config_raises_when_main_prompt_section_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(
                """[planner]
model = "openai:test"
base_url = "https://planner.example/v1"
api_key_env = "PLANNER_API_KEY"
timeout = 42
max_retries = 4
interrupt_on = {}
max_planning_rounds = 2
tool_budget = 4

[planner.context_agent_prompt]
system_file = "planner_context_agent_system.txt"
user_file = "planner_context_agent_user.txt"

[planner.resolution_agent_prompt]
system_file = "planner_resolution_agent_system.txt"
user_file = "planner_resolution_agent_user.txt"

[planner.evals]
world_state_file = "world_state.toml"

[search.api]
base_url = "https://search.example/v1"
api_key_env = "SEARCH_API_KEY"

[search.models]
dense_embedding = "dense"
sparse_embedding = "sparse"
reranker = "reranker"

[search.qdrant]
url = "http://qdrant.example:6333"
collection_name = "rules"
dense_vector_name = "dense"
sparse_vector_name = "sparse"

[search]
default_limit = 4
default_fetch_k = 11
rerank_timeout = 17.0
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectConfigError, "main_prompt"):
                load_project_config(config_path)

    def test_load_project_config_raises_when_evals_section_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(
                """[planner]
model = "openai:test"
base_url = "https://planner.example/v1"
api_key_env = "PLANNER_API_KEY"
timeout = 42
max_retries = 4
interrupt_on = {}
max_planning_rounds = 2
tool_budget = 4

[planner.main_prompt]
directory = "prompts"
system_file = "planner_system.txt"
user_file = "planner_user.txt"

[planner.context_agent_prompt]
system_file = "planner_context_agent_system.txt"
user_file = "planner_context_agent_user.txt"

[planner.resolution_agent_prompt]
system_file = "planner_resolution_agent_system.txt"
user_file = "planner_resolution_agent_user.txt"

[search.api]
base_url = "https://search.example/v1"
api_key_env = "SEARCH_API_KEY"

[search.models]
dense_embedding = "dense"
sparse_embedding = "sparse"
reranker = "reranker"

[search.qdrant]
url = "http://qdrant.example:6333"
collection_name = "rules"
dense_vector_name = "dense"
sparse_vector_name = "sparse"

[search]
default_limit = 4
default_fetch_k = 11
rerank_timeout = 17.0
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectConfigError, "evals"):
                load_project_config(config_path)

    def test_load_project_config_raises_for_missing_api_key_env_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = write_project_config(Path(temp_dir) / "config.toml")

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ProjectConfigError, "PLANNER_API_KEY"):
                    load_project_config(config_path)

    def test_resolve_path_from_config_uses_config_parent_for_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_path = write_project_config(config_dir / "config.toml")

            resolved = resolve_path_from_config("../examples/fetch_keys_state.json", config_path=config_path)

        self.assertEqual((Path(temp_dir) / "examples" / "fetch_keys_state.json").resolve(), resolved)

    def test_project_config_boundary_helpers_expose_governed_sections(self) -> None:
        self.assertIn("planner", PROJECT_LEVEL_CONFIG_SECTIONS)
        self.assertIn("field_maps", STATIC_FIXTURE_CATEGORIES)
        self.assertTrue(is_project_level_config_section("search"))
        self.assertFalse(is_project_level_config_section("demo_runner"))
        self.assertFalse(is_project_level_config_section("fetch_keys_script"))
        self.assertFalse(is_project_level_config_section("demo_fixtures"))


if __name__ == "__main__":
    unittest.main()
