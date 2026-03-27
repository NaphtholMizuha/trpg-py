## 新增需求

## 修改需求

### 需求:planner 必须基于 Deep Agents 实现
系统必须基于 LangChain 的 `create_agent()`/LangGraph agent runtime 实现 planner 主流程，禁止继续要求 planner 默认依赖 `deepagents.create_deep_agent()` 及其通用 coding-agent 默认 prompt/middleware 栈。planner 仍然必须能够在同一运行流中消费 `search`、`fetch_keys`、`reads` 与 `lint`，并输出结构化结果。

#### 场景:调用方通过 create_agent planner 执行规划
- **当** 调用方创建并运行 planner
- **那么** planner 默认由 `langchain.agents.create_agent()` 创建运行图
- **那么** planner 不再要求加载 deep agent 默认的待办清单、文件系统、子代理或补丁工具中间件
- **那么** planner 仍可在同一运行流中消费 `search`、`fetch_keys`、`reads` 与 `lint`
- **那么** planner 仍输出结构化 `PlannerResult`

### 需求:planner 必须提供 factory 统一模型接入与运行配置
系统必须提供 planner factory 作为统一创建入口，用于集中配置模型接入参数（如 `model`、`base_url`、`api_key`）以及运行参数（如 `timeout`、`max_retries`、`interrupt_on`）。系统禁止在业务调用点分散创建 planner agent 实例并重复硬编码接入参数。重构到底层 `create_agent()` 后，该 factory 仍必须保留现有配置解析优先级与 checkpointer/HITL 接线能力。

#### 场景:调用方通过 factory 注入自定义模型接入点
- **当** 调用方需要使用自定义 OpenAI 兼容 API 接入点
- **那么** 调用方可以通过 planner factory 注入 `base_url` 与 `api_key`
- **那么** planner 使用该配置创建 `create_agent()` 运行实例

#### 场景:factory 按统一优先级解析配置
- **当** 同一配置项同时存在调用参数、环境变量和默认值
- **那么** factory 必须按统一优先级解析（调用参数优先于环境变量，环境变量优先于默认值）
- **那么** planner 实例的运行配置可被稳定预测和复现

#### 场景:factory 保留中断恢复能力
- **当** planner 配置了 `interrupt_on` 或调用方显式传入 checkpointer
- **那么** factory 创建出的 planner 必须仍然支持同线程 resume 与等价的 HITL 中断恢复语义
- **那么** 调用方无需因 runtime 从 deep agent 切换到 `create_agent()` 而修改既有恢复调用方式

## 移除需求
