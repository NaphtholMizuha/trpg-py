## 新增需求

### 需求:主 agent 到 Context Agent 的默认委派输入必须可被独立评测脚本复现
系统必须保证主 agent 委派给 Context Agent 的默认输入契约可以被独立 eval 脚本直接复现和观察。系统禁止把该委派输入隐藏在只有主 workflow 才能访问的内部装配细节里。

#### 场景:开发者复现主 agent 的 Context Agent 委派
- **当** 开发者运行专门的 Context Agent eval 脚本
- **那么** 脚本必须能够构造与主 agent 默认委派语义一致的输入 payload
- **那么** 开发者必须能够直接观察该 payload 驱动下返回的 `ContextBundle`

## 修改需求

### 需求: planner 必须驻留在 agent 命名空间并以结构化接口对外
系统必须在 `augury.agent` 命名空间下提供 planner 能力，并以结构化输入输出接口供调用方使用，禁止仅通过临时 prompt、不可复用脚本或隐藏的内部委派格式触发规划流程。planner 的默认模型认证信息必须通过统一配置解析后的环境变量密钥获取，而不是要求调用方把密钥直接写入项目配置文件。对于主 agent 默认会委派给 Context Agent 的输入契约，系统必须允许维护者通过独立评测脚本在不运行完整 workflow 的前提下复现并观察该契约。

#### 场景:调用方以结构化方式发起规划
- **当** 调用方向 planner 提交 instruction、state 或其他结构化上下文
- **那么** 调用方可以通过 `augury.agent` 暴露的 planner 入口发起请求
- **那么** planner 返回结构化的 `ready`、`needs_human` 或 `blocked` 结果
- **那么** 调用方不需要依赖一次性脚本或内联 prompt 才能使用 planner

#### 场景:维护者独立观察 Context Agent 委派输入
- **当** 维护者需要定位 Context Agent 的上下文采集行为
- **那么** 系统必须允许其不运行完整 planner workflow 也能复现主 agent 默认委派给 Context Agent 的输入
- **那么** 该观察路径必须与正式 planner 的委派语义保持一致

## 移除需求
