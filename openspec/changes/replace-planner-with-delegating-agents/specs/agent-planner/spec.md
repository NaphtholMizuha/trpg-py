## 新增需求

## 修改需求

### 需求: planner 必须驻留在 agent 命名空间并以结构化接口对外
系统必须在 `augury.agent` 命名空间下提供 planner 能力，并以结构化输入输出接口供调用方使用。新的 planner 入口必须由主 agent 驱动，并以 `list_skills`、`load_skills`、`delegate` 工具完成能力发现与子 agent 委派；系统禁止继续把固定 smoke 入口或固定双节点流程当作对外使用真相。

#### 场景:调用方以结构化方式发起规划
- **当** 调用方向 planner 提交 instruction、state 或其他结构化上下文
- **那么** 调用方可以通过 `augury.agent` 暴露的 planner 入口发起请求
- **那么** planner 必须由主 agent 作为第一执行单元处理该请求
- **那么** planner 返回结构化的 `ready`、`needs_human`、`blocked` 或 `error` 结果
- **那么** 调用方不需要依赖一次性脚本、内联 prompt 或直接装配旧节点才能使用 planner

## 移除需求

### 需求: planner 必须提供可手动运行的集成测试脚本
**Reason**: 手动 smoke 脚本不再作为长期验证契约，新的验证真相将收敛到自动测试与版本化评测。
**Migration**: 将 `src/smoke/test_planner.py` 的观察面迁移到 `src/tests/` 与固定 eval fixtures，而不是保留独立 smoke 入口。

### 需求: planner 集成脚本必须帮助开发者观察代表性规划结果
**Reason**: 代表性结果观察应由自动测试与评测日志承担，而不是继续由手动脚本承担长期契约。
**Migration**: 将默认场景、结果摘要和日志能力迁移到 tests/evals 输出。

### 需求: planner smoke 脚本必须默认验证真实配置链路
**Reason**: 真实配置链路仍需验证，但不再通过 smoke 脚本表达长期规范。
**Migration**: 把配置链路验证迁移到自动测试和评测装配过程。

### 需求: planner smoke 脚本必须展示真实规划结果
**Reason**: 真实规划结果仍需可观察，但观察面不再以 smoke 脚本为长期契约。
**Migration**: 通过测试输出、结构化评测日志和主 agent 返回结果提供观察面。

### 需求: planner smoke 脚本必须从正常嵌套 TOML 载入默认 world state
**Reason**: world state 装载能力仍保留，但不再需要绑定到 smoke 脚本。
**Migration**: 将该要求迁移到正式 planner 入口、测试夹具或评测入口的状态装载逻辑。
