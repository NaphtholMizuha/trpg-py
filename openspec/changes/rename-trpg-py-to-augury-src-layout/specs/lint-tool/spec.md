## 新增需求

## 修改需求

### 需求:lint 工具必须驻留在 agent.tools 命名空间
系统必须在 `augury.agent.tools` 命名空间下提供名为 `lint` 的工具能力，并且该能力必须可以被 Python 调用方直接导入和使用，而不是仅作为 planner 内部私有辅助函数存在。

#### 场景:调用方从 agent.tools 使用 lint
- **当** 开发者为 planner 或其他 agent 组装工具集
- **那么** 可以从 `augury.agent.tools` 访问 `lint` 工具实现
- **那么** 调用方不需要自行拼装任务文档校验逻辑

## 移除需求
