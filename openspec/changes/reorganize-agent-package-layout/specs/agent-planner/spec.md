## 新增需求

## 修改需求

### 需求: planner 必须驻留在 agent 命名空间并以结构化接口对外
系统必须在 `augury.agent` 命名空间下提供 planner 能力，并以结构化输入输出接口供调用方使用。新的 planner 入口必须由主 agent 作为第一执行单元处理请求，并以 `list_skills`、`load_skills`、`delegate` 工具完成能力发现与子 agent 委派。系统必须通过 `augury.agent` 包根维持稳定公共 API，禁止要求调用方长期依赖 `augury.agent.runtime` 这类内部文件路径才能使用 planner。

#### 场景:调用方以结构化方式发起规划
- **当** 调用方向 planner 提交 instruction、state 或其他结构化上下文
- **那么** 调用方可以通过 `augury.agent` 暴露的 planner 入口发起请求
- **那么** planner 必须由主 agent 作为第一执行单元处理该请求
- **那么** planner 返回结构化的 `ready`、`needs_human`、`blocked` 或 `error` 结果
- **那么** 调用方不需要依赖一次性脚本、内联 prompt 或直接装配旧节点才能使用 planner

#### 场景:维护者调整 planner 内部文件布局
- **当** 维护者重构 `augury.agent` 包内的模块命名或目录结构
- **那么** `augury.agent` 包根仍必须继续暴露稳定的 planner 公共符号
- **那么** 系统不得要求调用方因为内部文件重命名而改为直接导入内部实现模块

## 移除需求
