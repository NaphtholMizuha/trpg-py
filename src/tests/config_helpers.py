from __future__ import annotations

from pathlib import Path


def write_project_config(
    path: Path,
    *,
    planner_model: str = "openai:test-planner",
    planner_base_url: str = "https://planner.example/v1",
    planner_api_key_env: str = "PLANNER_API_KEY",
    planner_timeout: float = 42.0,
    planner_max_retries: int = 5,
    planner_interrupt_on: str = "{ human = true }",
    planner_max_planning_rounds: int = 3,
    planner_tool_budget: int = 7,
    planner_prompt_directory: str = "prompts",
    planner_prompt_system_file: str = "planner_system.txt",
    planner_prompt_user_file: str = "planner_user.txt",
    planner_system_prompt_template: str = "System prompt budget {{tool_budget}}",
    planner_user_prompt_template: str = (
        "Instruction: {{instruction}}\n"
        "Context: {{context_json}}\n"
        "Policy: {{policy_json}}\n"
        "Budget: {{tool_budget}}\n"
        "Repair: {{validation_feedback}}"
    ),
    planner_task_node_system_file: str = "planner_task_node_system.txt",
    planner_task_node_user_file: str = "planner_task_node_user.txt",
    planner_task_node_system_prompt_template: str = "Task node system prompt",
    planner_task_node_user_prompt_template: str = "Task node user prompt: {{instruction}}",
    planner_dsl_node_system_file: str = "planner_dsl_node_system.txt",
    planner_dsl_node_user_file: str = "planner_dsl_node_user.txt",
    planner_dsl_node_system_prompt_template: str = "DSL node system prompt",
    planner_dsl_node_user_prompt_template: str = "DSL node user prompt: {{task_draft_json}}",
    planner_smoke_world_state_file: str = "world_state.toml",
    planner_smoke_world_state_template: str = (
        "[actors.goblin_1]\n"
        "id = \"goblin_1\"\n"
        "ac = 13\n"
        "hp = { current = 7, max = 7 }\n"
        "\n"
        "[actors.goblin_1.attacks.scimitar]\n"
        "to_hit = 4\n"
        "damage = [{ dice = \"1d6\", bonus = 2, damage_type = \"slashing\" }]\n"
        "\n"
        "[actors.hero_1]\n"
        "id = \"hero_1\"\n"
        "ac = 16\n"
        "hp = { current = 20, max = 20 }\n"
    ),
    search_base_url: str = "https://search.example/v1",
    search_api_key_env: str = "SEARCH_API_KEY",
    search_dense_embedding: str = "dense-model",
    search_sparse_embedding: str = "sparse-model",
    search_reranker: str = "reranker-model",
    search_qdrant_url: str = "http://qdrant.example:6333",
    search_collection_name: str = "rules",
    search_dense_vector_name: str = "dense_vec",
    search_sparse_vector_name: str = "sparse_vec",
    search_default_limit: int = 4,
    search_default_fetch_k: int = 11,
    search_rerank_timeout: float = 17.0,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    prompt_dir = path.parent / planner_prompt_directory
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / planner_prompt_system_file).write_text(
        planner_system_prompt_template,
        encoding="utf-8",
    )
    (prompt_dir / planner_prompt_user_file).write_text(
        planner_user_prompt_template,
        encoding="utf-8",
    )
    (prompt_dir / planner_task_node_system_file).write_text(
        planner_task_node_system_prompt_template,
        encoding="utf-8",
    )
    (prompt_dir / planner_task_node_user_file).write_text(
        planner_task_node_user_prompt_template,
        encoding="utf-8",
    )
    (prompt_dir / planner_dsl_node_system_file).write_text(
        planner_dsl_node_system_prompt_template,
        encoding="utf-8",
    )
    (prompt_dir / planner_dsl_node_user_file).write_text(
        planner_dsl_node_user_prompt_template,
        encoding="utf-8",
    )
    (path.parent / planner_smoke_world_state_file).write_text(
        planner_smoke_world_state_template,
        encoding="utf-8",
    )
    path.write_text(
        f"""[planner]
model = \"{planner_model}\"
base_url = \"{planner_base_url}\"
api_key_env = \"{planner_api_key_env}\"
timeout = {planner_timeout}
max_retries = {planner_max_retries}
interrupt_on = {planner_interrupt_on}
max_planning_rounds = {planner_max_planning_rounds}
tool_budget = {planner_tool_budget}

[planner.prompt]
directory = "{planner_prompt_directory}"
system_file = "{planner_prompt_system_file}"
user_file = "{planner_prompt_user_file}"

[planner.task_node_prompt]
system_file = "{planner_task_node_system_file}"
user_file = "{planner_task_node_user_file}"

[planner.dsl_node_prompt]
system_file = "{planner_dsl_node_system_file}"
user_file = "{planner_dsl_node_user_file}"

[planner.smoke]
world_state_file = "{planner_smoke_world_state_file}"

[search.api]
base_url = \"{search_base_url}\"
api_key_env = \"{search_api_key_env}\"

[search.models]
dense_embedding = \"{search_dense_embedding}\"
sparse_embedding = \"{search_sparse_embedding}\"
reranker = \"{search_reranker}\"

[search.qdrant]
url = \"{search_qdrant_url}\"
collection_name = \"{search_collection_name}\"
dense_vector_name = \"{search_dense_vector_name}\"
sparse_vector_name = \"{search_sparse_vector_name}\"

[search]
default_limit = {search_default_limit}
default_fetch_k = {search_default_fetch_k}
rerank_timeout = {search_rerank_timeout}
""",
        encoding="utf-8",
    )
    return path
