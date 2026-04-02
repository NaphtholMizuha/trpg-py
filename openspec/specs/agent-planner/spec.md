# agent-planner 规范

## 目的
定义对外暴露的 planner 能力、手动 smoke 入口以及默认配置与世界状态加载约束，确保调用方可以通过稳定的 `augury.agent` 接口使用真实 planner 链路。

## 需求
### 需求: planner 必须驻留在 agent 命名空间并以结构化接口对外
系统必须在 `augury.agent` 命名空间下提供 planner 能力，并以结构化输入输出接口供调用方使用，禁止仅通过临时 prompt 或不可复用脚本触发规划流程。planner 的默认模型认证信息必须通过统一配置解析后的环境变量密钥获取，而不是要求调用方把密钥直接写入项目配置文件。

#### 场景:调用方以结构化方式发起规划
- **当** 调用方向 planner 提交 instruction、state 或其他结构化上下文
- **那么** 调用方可以通过 `augury.agent` 暴露的 planner 入口发起请求
- **那么** planner 返回结构化的 `ready`、`needs_human` 或 `blocked` 结果
- **那么** 调用方不需要依赖一次性脚本或内联 prompt 才能使用 planner

### 需求: planner 必须提供可手动运行的集成测试脚本
系统必须提供一个位于 `src/smoke/test_planner.py` 的可手动运行脚本，用于让开发者直接观察 planner 的结构化效果，禁止要求开发者只能通过单元测试或临时代码片段验证 planner 行为。该脚本必须以真实 planner 配置链路和真实工具链路作为默认运行路径，而不是以内置 fake 响应模拟结果。

#### 场景:开发者手动运行 planner 集成脚本
- **当** 开发者执行 `src/smoke/test_planner.py` 并提供 DM 指令或示例场景
- **那么** 脚本调用 `augury.agent` 暴露的 planner 能力发起一次真实规划
- **那么** 规划过程使用真实 `search` 与真实 `fetch_keys`
- **那么** 输出中展示真实返回的 `ready`、`needs_human` 或 `blocked` 等结构化状态

### 需求: planner 集成脚本必须帮助开发者观察代表性规划结果
系统必须让 planner 集成脚本支持至少一个可复现示例场景，并能够向开发者清晰展示 `task_document`、澄清问题或阻塞原因等核心结果。该结果必须来源于真实调用，而不是脚本预制的假响应。默认示例场景必须使用一份足够丰富的 world state 文件，而不是继续使用只含少量字段的内联最小 state。

#### 场景:脚本展示 planner 结果摘要
- **当** planner 集成脚本完成一次规划请求
- **那么** 调用方可以从输出中看出 planner 返回的真实状态类型
- **那么** 调用方可以查看对应的真实 `task_document`、`questions` 或 `error` 摘要

#### 场景:脚本使用更真实的默认世界状态
- **当** 开发者直接运行 `src/smoke/test_planner.py`
- **那么** 脚本必须从配置指定的默认 world state 文件加载示例状态
- **那么** 该状态必须覆盖比当前极简内联 state 更完整的角色、战斗或环境信息
- **那么** 脚本不得继续把内联最小字典作为默认真相

### 需求: planner smoke 脚本必须默认验证真实配置链路
系统必须让 `src/smoke/test_planner.py` 默认读取项目统一配置并构造真实 planner，禁止以内置 fake agent、fake LLM、fake tool 或脚本预制结果作为默认 smoke 路径。默认 smoke 状态也必须通过配置指定的 world state 文件提供，并在加载后转换为真实 planner 使用的 state 结构。

#### 场景:开发者直接运行 planner smoke 脚本
- **当** 开发者执行 `python src/smoke/test_planner.py`
- **那么** 脚本必须读取 `config/config.toml` 或显式传入的配置路径
- **那么** 脚本必须通过 `augury.agent.create_planner(...)` 构造真实 planner
- **那么** 规划过程中必须使用真实 `search` 与真实 `fetch_keys` 工具链路
- **那么** 默认 state 必须来自配置指定的 world state 文件而不是内联常量
- **那么** 脚本不得默认返回脚本内部伪造的规划结果

### 需求: planner smoke 脚本必须展示真实规划结果
系统必须让 `src/smoke/test_planner.py` 的输出直接来源于真实 planner 调用结果，禁止把预制 `ready`、`needs_human` 或 `blocked` 响应当作 smoke 输出真相。对于 `needs_human` 中由内部 `TaskDocument` 校验失败触发的场景，默认人类可读摘要也必须展示具体失败原因，禁止只剩泛化问题和抽象 reason。

#### 场景:脚本输出真实 planner 结果
- **当** planner smoke 脚本完成一次规划调用
- **那么** 人类可读摘要或 JSON 输出必须展示真实返回的 `status`
- **那么** 若返回 `ready`，输出中必须可见真实 `task_document` 摘要或正文
- **那么** 若返回 `needs_human` 或 `blocked`，输出中必须可见真实问题列表或错误信息

#### 场景:默认摘要展示内部文档失败原因
- **当** planner smoke 脚本返回 `status=needs_human` 且 `reason=task_document_validation`
- **那么** 非 `--debug` 的默认人类可读输出必须展示最后一次文档校验失败原因
- **那么** 调用方无需切换到 JSON 或 `--debug` 才能知道该产物为何不是合法 `TaskDocument`

### 需求: planner smoke 脚本必须从正常嵌套 TOML 载入默认 world state
系统必须让 `src/smoke/test_planner.py` 在读取默认 world state 文件时直接消费正常嵌套 TOML 结构，禁止继续要求默认 fixture 以扁平点路径键格式书写。

#### 场景:planner smoke 读取默认 world state
- **当** 开发者运行 `src/smoke/test_planner.py` 且默认 state 来源为 `config/world_state.toml`
- **那么** 脚本可以直接从嵌套 TOML 解析结果构造 planner 使用的 state
- **那么** 脚本不再依赖“顶层 TOML key 本身是点路径”这一特殊约定
