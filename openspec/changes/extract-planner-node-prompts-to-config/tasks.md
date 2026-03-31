## 1. Prompt Files

- [x] 1.1 在 `config/config.toml` 中为 `task_node` 增加独立的 `system_file` 与 `user_file` 配置。
- [x] 1.2 在 `config/config.toml` 中为 `dsl_node` 增加独立的 `system_file` 与 `user_file` 配置。
- [x] 1.3 在 `config/prompts/` 下新增 `task_node` 的 system prompt 文件与 user prompt 模板文件。
- [x] 1.4 在 `config/prompts/` 下新增 `dsl_node` 的 system prompt 文件与 user prompt 模板文件。

## 2. Prompt Loading

- [x] 2.1 为 planner node 增加统一的 prompt 加载辅助逻辑，默认从配置文件解析 prompt 内容。
- [x] 2.2 重构 `src/augury/planner/nodes/task_node.py`，让它默认从配置文件指定的 system/user prompt 文件读取模板，并保留显式传入 prompt 的覆写能力。
- [x] 2.3 重构 `src/augury/planner/nodes/dsl_node.py`，让它默认从配置文件指定的 system/user prompt 文件读取模板，并保留显式传入 prompt 的覆写能力。

## 3. Validation

- [x] 3.1 更新或新增测试，验证两个 node 在默认情况下会按照 `config/config.toml` 读取各自的 system/user prompt 文件。
- [x] 3.2 更新或新增测试，验证显式传入的 prompt 会覆盖文件默认值。
