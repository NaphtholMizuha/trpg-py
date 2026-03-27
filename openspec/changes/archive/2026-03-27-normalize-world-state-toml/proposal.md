## 为什么

当前 `config/world_state.toml` 采用“带引号的点路径 key”作为顶层键，例如 `"actors.goblin_1.ac" = 13`。这种写法虽然方便脚本通过 `set_path(...)` 重建嵌套 state，但它并不是正常的层级化 TOML 书写方式，可读性差，也让人难以把世界状态当作一份自然的静态数据文件维护。

这份文件现在既服务于 planner smoke，也被 `reads` 等脚本直接读取。随着 planner 越来越依赖 world state 进行真实规划，默认示例状态需要更易读、易维护、易扩展，同时不能破坏现有 `store`、`fetch_keys`、`reads`、planner 与 engine 依赖的点路径访问语义。

## 变更内容

- 将默认 `config/world_state.toml` 从扁平点路径键格式迁移为正常的嵌套 TOML 结构，例如使用 `[actors.goblin_1]`、`[actors.aldera.abilities.str]` 等层级表。
- 调整依赖该文件的加载逻辑，使 smoke/planner/reads 等入口直接消费嵌套 TOML 解析结果，而不再假设顶层键本身就是点路径。
- 保持运行时 state 的嵌套字典/列表结构与现有点路径语义兼容，确保 `fetch_keys`、`reads`、执行器引用解析和现有 store 接口不需要改变其外部契约。
- 同步更新测试夹具、默认示例与文档，确保仓库内所有默认 world state fixture 都采用同一正常 TOML 约定。

## 功能 (Capabilities)

### 新增功能
- `planner-world-state-fixture`: 定义 planner 默认 world state fixture 的正常 TOML 结构、加载语义和迁移边界。

### 修改功能
- `agent-planner`: planner smoke 默认 world state 的加载方式需要适配正常嵌套 TOML，而不是只支持扁平点路径键。
- `reads-tool`: `reads` smoke 入口需要适配正常嵌套 TOML fixture 作为默认状态来源。
- `planner-execution-smoke`: planner + engine 端到端 smoke 入口需要适配新的默认 world state fixture 结构。

## 影响

- `config/world_state.toml` 的文件格式与可维护性。
- `smoke/test_planner.py`、`smoke/test_planner_engine.py`、`smoke/test_reads.py` 等 world state 读取入口。
- 测试夹具中默认 world state 模板的写法，例如 `tests/config_helpers.py`。
- 与默认 world state 说明相关的 README/文档。
