## 新增需求

### 需求:planner smoke 脚本必须默认验证真实配置链路
系统必须让 `smoke/test_planner.py` 默认读取项目统一配置并构造真实 planner，禁止以内置 fake agent、fake LLM、fake tool 或脚本预制结果作为默认 smoke 路径。

#### 场景:开发者直接运行 planner smoke 脚本
- **当** 开发者执行 `python smoke/test_planner.py`
- **那么** 脚本必须读取 `config/config.toml` 或显式传入的配置路径
- **那么** 脚本必须通过 `trpg_py.agent.create_planner(...)` 构造真实 planner
- **那么** 规划过程中必须使用真实 `search` 与真实 `fetch_keys` 工具链路
- **那么** 脚本不得默认返回脚本内部伪造的规划结果

### 需求:planner smoke 脚本必须展示真实规划结果
系统必须让 `smoke/test_planner.py` 的输出直接来源于真实 planner 调用结果，禁止把预制 `ready`、`needs_human` 或 `blocked` 响应当作 smoke 输出真相。

#### 场景:脚本输出真实 planner 结果
- **当** planner smoke 脚本完成一次规划调用
- **那么** 人类可读摘要或 JSON 输出必须展示真实返回的 `status`
- **那么** 若返回 `ready`，输出中必须可见真实 `task_document` 摘要或正文
- **那么** 若返回 `needs_human` 或 `blocked`，输出中必须可见真实问题列表或错误信息

## 修改需求

### 需求:planner 必须提供可手动运行的集成测试脚本
系统必须提供一个位于 `smoke/test_planner.py` 的可手动运行脚本，用于让开发者直接观察 planner 的结构化效果，禁止要求开发者只能通过单元测试或临时代码片段验证 planner 行为。该脚本必须以真实 planner 配置链路和真实工具链路作为默认运行路径，而不是以内置 fake 响应模拟结果。

#### 场景:开发者手动运行 planner 集成脚本
- **当** 开发者执行 `smoke/test_planner.py` 并提供 DM 指令或示例场景
- **那么** 脚本调用 `trpg_py.agent` 暴露的 planner 能力发起一次真实规划
- **那么** 规划过程使用真实 `search` 与真实 `fetch_keys`
- **那么** 输出中展示真实返回的 `ready`、`needs_human` 或 `blocked` 等结构化状态

### 需求:planner 集成脚本必须帮助开发者观察代表性规划结果
系统必须让 planner 集成脚本支持至少一个可复现示例场景，并能够向开发者清晰展示 `task_document`、澄清问题或阻塞原因等核心结果。该结果必须来源于真实调用，而不是脚本预制的假响应。

#### 场景:脚本展示 planner 结果摘要
- **当** planner 集成脚本完成一次规划请求
- **那么** 调用方可以从输出中看出 planner 返回的真实状态类型
- **那么** 调用方可以查看对应的真实 `task_document`、`questions` 或 `error` 摘要

## 移除需求
