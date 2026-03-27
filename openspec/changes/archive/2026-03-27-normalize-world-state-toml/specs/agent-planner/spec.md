# agent-planner 规范变更

## 修改需求
### 需求:planner smoke 脚本必须从正常嵌套 TOML 载入默认 world state
系统必须让 `smoke/test_planner.py` 在读取默认 world state 文件时直接消费正常嵌套 TOML 结构，禁止继续要求默认 fixture 以扁平点路径键格式书写。

#### 场景:planner smoke 读取默认 world state
- **当** 开发者运行 `smoke/test_planner.py` 且默认 state 来源为 `config/world_state.toml`
- **那么** 脚本可以直接从嵌套 TOML 解析结果构造 planner 使用的 state
- **那么** 脚本不再依赖“顶层 TOML key 本身是点路径”这一特殊约定
