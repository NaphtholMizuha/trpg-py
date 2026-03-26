## 1. 依赖与日志约定

- [x] 1.1 将 `loguru` 添加到项目依赖，并确定 agent 工具调用日志的基础字段约定
- [x] 1.2 为工具日志明确输入摘要、输出状态摘要和错误信息的记录边界，避免泄漏敏感信息或无边界打印大对象

## 2. 工具调用日志实现

- [x] 2.1 在 `trpg_py/agent/tools/search.py` 中为每次工具调用增加 loguru 输入/输出日志，覆盖 `ok`、`no_match` 和 `error`
- [x] 2.2 在 `trpg_py/agent/tools/fetch_keys.py` 中为每次工具调用增加 loguru 输入/输出日志，覆盖 `ok`、`no_match` 和 `error`
- [x] 2.3 确认 planner 通过现有工具调用链路即可获得这些日志，而不需要在 planner 层重复实现同类日志

## 3. 验证与说明

- [x] 3.1 为 `search` 与 `fetch_keys` 增加或调整测试，验证调用日志在成功、无命中和错误分支均会产生
- [x] 3.2 视需要更新 README 或 smoke 说明，告知开发者工具调用会通过 loguru 自动记录
- [x] 3.3 运行相关测试并记录仍未覆盖的真实外部依赖日志行为限制
