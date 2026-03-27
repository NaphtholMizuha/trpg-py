## 1. World State Fixture 迁移

- [x] 1.1 将 `config/world_state.toml` 从扁平点路径键格式改写为正常嵌套 TOML
- [x] 1.2 校对迁移后的默认 fixture 在语义上与现有示例状态保持一致，避免角色、资源或位置字段丢失

## 2. Loader 与 Smoke 适配

- [x] 2.1 更新 `smoke/test_planner.py` 的 world state 加载逻辑，使其直接消费嵌套 TOML 结果而不再依赖 `set_path(...)` 展开顶层点路径键
- [x] 2.2 更新 `smoke/test_reads.py` 以及其他默认读取 `world_state.toml` 的入口，适配新的嵌套 TOML 结构
- [x] 2.3 验证 planner + engine 端到端 smoke 在新默认 fixture 下仍能完成 world state 载入与执行链路

## 3. 夹具、测试与文档

- [x] 3.1 更新 `tests/config_helpers.py` 等测试辅助中的默认 world state 模板，使其与新的嵌套 TOML 约定一致
- [x] 3.2 补充或更新单元测试 / smoke 测试，覆盖新格式 world state 的默认加载
- [x] 3.3 更新 README 或相关说明，明确默认 world state 现采用正常嵌套 TOML
