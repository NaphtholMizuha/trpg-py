## 新增需求

## 修改需求

### 需求: planner 必须驻留在 agent 命名空间并以结构化接口对外
系统必须在 `augury.agent` 命名空间下提供 planner 能力，并以结构化输入输出接口供调用方使用。新的 planner 入口必须由主 agent 驱动，并以 `list_skills`、`load_skills`、`delegate` 工具完成能力发现与子 agent 委派。系统必须通过 `augury.agent` 包根维持稳定公共 API，禁止继续把 `augury.agent.runtime`、`augury.agent.context_eval`、`augury.agent.evals` 等根级兼容 shim 作为新的长期入口真相。

#### 场景:调用方以结构化方式发起规划
- **当** 调用方向 planner 提交 instruction、state 或其他结构化上下文
- **那么** 调用方可以通过 `augury.agent` 暴露的 planner 入口发起请求
- **那么** planner 必须由主 agent 作为第一执行单元处理该请求
- **那么** planner 返回结构化的 `ready`、`needs_human`、`blocked` 或 `error` 结果
- **那么** 调用方不需要依赖一次性脚本、内联 prompt 或直接装配旧节点才能使用 planner

#### 场景:维护者清理 agent 包根过渡文件
- **当** 维护者清理 `augury.agent` 包根中的历史兼容 shim
- **那么** `augury.agent` 包根仍必须继续暴露稳定的 planner 公共符号
- **那么** 系统不得要求维护者把根级 shim 继续保留为长期公共 API 入口

## 移除需求
