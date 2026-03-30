from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.config_helpers import write_project_config
from augury.config import (
    PROJECT_LEVEL_CONFIG_SECTIONS,
    ProjectConfigError,
    STATIC_FIXTURE_CATEGORIES,
    clear_project_config_cache,
    is_project_level_config_section,
    load_project_config,
    resolve_path_from_config,
)


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
        self.assertEqual("prompts", first.planner.prompt.directory)
        self.assertEqual("planner_system.txt", first.planner.prompt.system_file)
        self.assertEqual("world_state.toml", first.planner.smoke.world_state_file)
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
                """[planner]\nmodel = \"openai:test\"\nbase_url = \"https://planner.example/v1\"\napi_key_env = \"PLANNER_API_KEY\"\ntimeout = 42\nmax_retries = \"oops\"\ninterrupt_on = {}\nmax_planning_rounds = 2\ntool_budget = 4\n\n[planner.prompt]\ndirectory = \"prompts\"\nsystem_file = \"planner_system.txt\"\nuser_file = \"planner_user.txt\"\n\n[planner.smoke]\nworld_state_file = \"world_state.toml\"\n\n[search.api]\nbase_url = \"https://search.example/v1\"\napi_key_env = \"SEARCH_API_KEY\"\n\n[search.models]\ndense_embedding = \"dense\"\nsparse_embedding = \"sparse\"\nreranker = \"reranker\"\n\n[search.qdrant]\nurl = \"http://qdrant.example:6333\"\ncollection_name = \"rules\"\ndense_vector_name = \"dense\"\nsparse_vector_name = \"sparse\"\n\n[search]\ndefault_limit = 4\ndefault_fetch_k = 11\nrerank_timeout = 17.0\n""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectConfigError, "max_retries"):
                load_project_config(config_path)

    def test_load_project_config_raises_when_prompt_section_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(
                """[planner]\nmodel = \"openai:test\"\nbase_url = \"https://planner.example/v1\"\napi_key_env = \"PLANNER_API_KEY\"\ntimeout = 42\nmax_retries = 4\ninterrupt_on = {}\nmax_planning_rounds = 2\ntool_budget = 4\n\n[planner.smoke]\nworld_state_file = \"world_state.toml\"\n\n[search.api]\nbase_url = \"https://search.example/v1\"\napi_key_env = \"SEARCH_API_KEY\"\n\n[search.models]\ndense_embedding = \"dense\"\nsparse_embedding = \"sparse\"\nreranker = \"reranker\"\n\n[search.qdrant]\nurl = \"http://qdrant.example:6333\"\ncollection_name = \"rules\"\ndense_vector_name = \"dense\"\nsparse_vector_name = \"sparse\"\n\n[search]\ndefault_limit = 4\ndefault_fetch_k = 11\nrerank_timeout = 17.0\n""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectConfigError, "prompt"):
                load_project_config(config_path)

    def test_load_project_config_raises_when_smoke_section_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(
                """[planner]\nmodel = \"openai:test\"\nbase_url = \"https://planner.example/v1\"\napi_key_env = \"PLANNER_API_KEY\"\ntimeout = 42\nmax_retries = 4\ninterrupt_on = {}\nmax_planning_rounds = 2\ntool_budget = 4\n\n[planner.prompt]\ndirectory = \"prompts\"\nsystem_file = \"planner_system.txt\"\nuser_file = \"planner_user.txt\"\n\n[search.api]\nbase_url = \"https://search.example/v1\"\napi_key_env = \"SEARCH_API_KEY\"\n\n[search.models]\ndense_embedding = \"dense\"\nsparse_embedding = \"sparse\"\nreranker = \"reranker\"\n\n[search.qdrant]\nurl = \"http://qdrant.example:6333\"\ncollection_name = \"rules\"\ndense_vector_name = \"dense\"\nsparse_vector_name = \"sparse\"\n\n[search]\ndefault_limit = 4\ndefault_fetch_k = 11\nrerank_timeout = 17.0\n""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectConfigError, "smoke"):
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
