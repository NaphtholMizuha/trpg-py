# planner-execution-smoke 规范

## 目的
定义从 planner 到 engine 的端到端手动 smoke 入口，确保开发者能在一次运行中观察 instruction、TaskDocument 和最终状态变化。

## 需求
### 需求: 系统必须提供 planner 到 engine 的端到端 smoke 入口
系统必须提供一个位于 `src/smoke/` 目录下的手动可运行脚本 `src/smoke/test_planner_engine.py`，用于把 DM instruction 先交给 planner 生成 `TaskDocument`，再在 `status=ready` 时把该文档交给 engine 执行。系统禁止继续要求开发者手工在 `test_planner` 与 `test_engine` 之间搬运中间 `TaskDocument` 才能验证最终状态变化。

#### 场景:开发者一次运行观察 instruction 到状态变化
- **当** 开发者执行新的 planner+engine smoke 脚本并提供 instruction
- **那么** 脚本先调用真实 planner 获取结构化规划结果
- **那么** 若 planner 返回 `status=ready`，脚本继续执行该 `task_document`
- **那么** 输出中可见最终执行状态和关键 state 变更摘要

### 需求: planner 到 engine 的端到端 smoke 必须支持正常嵌套 TOML world state
系统必须让 planner + engine 端到端 smoke 入口读取正常嵌套 TOML 的默认 world state fixture，而不是继续绑定到扁平点路径键格式。

#### 场景:开发者运行 planner + engine smoke
- **当** 开发者执行 `src/smoke/test_planner_engine.py` 且使用默认 world state 文件
- **那么** 脚本能在新的嵌套 TOML fixture 下成功加载默认 state
- **那么** 后续 planner 与 engine 仍基于既有点路径 state 语义运行
