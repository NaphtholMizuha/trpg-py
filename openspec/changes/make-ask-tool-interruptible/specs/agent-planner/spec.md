## 新增需求

## 修改需求

### 需求:planner 必须通过主 agent 委派 Context Agent 与 Resolution Agent
系统必须将 planner 的长期行为定义为主 agent 通过 `load_skills` / `list_skills` / `delegate` 调度子 agent。系统禁止继续把固定 planner 节点图作为长期唯一编排真相。

#### 场景:主 agent 处理一条可直接结算的战斗意图
- **当** 用户提供一条可由当前规则和世界状态直接支持的战斗意图
- **那么** planner 必须由主 agent 委派 Context Agent 收集上下文
- **那么** planner 必须在上下文齐备后再委派 Resolution Agent 生成和执行结果

### 需求:planner 必须在 ask 恢复后继续完成 Context Agent 结果生成
系统必须允许 Context Agent 在 ask 触发 interrupt 后，于恢复时带着 `AskResponse` 继续完成上下文收集。系统禁止把 ask 之后的控制流长期停留在“仅返回 ask 请求、由外层人工拼装后续结果”的模式。

#### 场景:Context Agent 通过 ask 消除目标歧义
- **当** Context Agent 因目标歧义触发 ask interrupt，且宿主提供目标选择回答
- **那么** Context Agent 必须在恢复后使用该回答继续整理规则证据和状态证据
- **那么** planner 必须能够得到 ask 之后更新过的 `ContextBundle`

#### 场景:CLI 宿主以同步方式完成 ask 后继续 planner
- **当** Python CLI 宿主在同一次运行中同步收集 ask 回答
- **那么** planner 必须在同一次运行中恢复 Context Agent 并继续生成结果
- **那么** 调用方不需要手工拼接第二次 Context Agent 调用才能得到 ask 后结果

## 移除需求
