## 新增需求

## 修改需求

### 需求:planner 必须驻留在 agent 命名空间并以结构化接口对外
系统必须在 `augury.agent` 命名空间下提供 planner 能力，并以结构化输入输出接口供调用方使用，禁止仅通过临时 prompt、不可复用脚本或隐藏的内部委派格式触发规划流程。planner 的默认模型认证信息必须通过统一配置解析后的环境变量密钥获取，而不是要求调用方把密钥直接写入项目配置文件。对于主 agent 默认会委派给 Context Agent 的输入契约，系统必须要求主 agent 将用户原始意图整理为 `intent`、`goal`、`requests` 形式的事实获取任务，并在需要 DM 澄清时显式暴露结构化 `ask_requests`，而不是继续依赖普通缺口文本。

#### 场景:调用方以结构化方式发起规划
- **当** 调用方向 planner 提交 instruction、state 或其他结构化上下文
- **那么** 调用方可以通过 `augury.agent` 暴露的 planner 入口发起请求
- **那么** planner 返回结构化的 `ready`、`needs_human` 或 `blocked` 结果
- **那么** 调用方不需要依赖一次性脚本或内联 prompt 才能使用 planner

#### 场景:planner 暴露 DM 澄清请求
- **当** Context Agent 或其他子 agent 生成 ask 请求来向 DM 确认关键背景
- **那么** planner 对外结果必须显式包含这些 ask 请求或等价结构
- **那么** 调用方不需要从 `notes` 或自由文本缺口中解析 ask 信息

#### 场景:当前通过 Python CLI 消费 ask
- **当** 当前运行宿主是 Python CLI
- **那么** planner 必须能够通过统一 ask 契约把澄清请求交给 CLI 层展示与回填
- **那么** planner 对外 ask 字段不得依赖 CLI 私有的数据形状

## 移除需求
