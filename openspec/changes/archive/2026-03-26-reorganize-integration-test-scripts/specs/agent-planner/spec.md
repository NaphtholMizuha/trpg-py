## 新增需求

### 需求:planner 必须提供可手动运行的集成测试脚本
系统必须提供一个位于 `smoke/test_planner.py` 的可手动运行脚本，用于让开发者直接观察 planner 的结构化效果，禁止要求开发者只能通过单元测试或临时代码片段验证 planner 行为。

#### 场景:开发者手动运行 planner 集成脚本
- **当** 开发者执行 `smoke/test_planner.py` 并提供 DM 指令或示例场景
- **那么** 脚本调用 `trpg_py.agent` 暴露的 planner 能力发起一次规划
- **那么** 输出中展示 `ready`、`needs_human` 或 `blocked` 等结构化状态

### 需求:planner 集成脚本必须帮助开发者观察代表性规划结果
系统必须让 planner 集成脚本支持至少一个可复现示例场景，并能够向开发者清晰展示 `task_document`、澄清问题或阻塞原因等核心结果。

#### 场景:脚本展示 planner 结果摘要
- **当** planner 集成脚本完成一次规划请求
- **那么** 调用方可以从输出中看出 planner 返回的状态类型
- **那么** 调用方可以查看对应的 `task_document`、`questions` 或 `error` 摘要

## 修改需求

## 移除需求
