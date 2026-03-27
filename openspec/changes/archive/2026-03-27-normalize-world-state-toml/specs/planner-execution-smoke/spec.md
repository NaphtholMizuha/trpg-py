# planner-execution-smoke 规范变更

## 修改需求
### 需求:planner 到 engine 的端到端 smoke 必须支持正常嵌套 TOML world state
系统必须让 planner + engine 端到端 smoke 入口读取正常嵌套 TOML 的默认 world state fixture，而不是继续绑定到扁平点路径键格式。

#### 场景:开发者运行 planner + engine smoke
- **当** 开发者执行 `smoke/test_planner_engine.py` 且使用默认 world state 文件
- **那么** 脚本能在新的嵌套 TOML fixture 下成功加载默认 state
- **那么** 后续 planner 与 engine 仍基于既有点路径 state 语义运行
