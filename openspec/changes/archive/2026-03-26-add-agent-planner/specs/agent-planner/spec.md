## 新增需求

### 需求:planner 必须基于 Deep Agents 实现
系统必须基于 LangChain 的 Deep Agents（`deepagents`）实现 planner 主流程，禁止将第一版 planner 实现为仅依赖基础 LangChain agent loop 的自由编排方案。

#### 场景:调用方通过 Deep Agents planner 执行规划
- **当** 调用方创建并运行 planner
- **那么** planner 由 Deep Agents 承载规划与工具编排能力
- **那么** planner 可在同一运行流中消费 `search`、`fetch_keys` 并输出结构化结果

### 需求:planner 必须提供 factory 统一模型接入与运行配置
系统必须提供 planner factory 作为统一创建入口，用于集中配置模型接入参数（如 `model`、`base_url`、`api_key`）以及运行参数（如 `timeout`、`max_retries`、`interrupt_on`）。系统禁止在业务调用点分散创建 Deep Agents 实例并重复硬编码接入参数。

#### 场景:调用方通过 factory 注入自定义模型接入点
- **当** 调用方需要使用自定义 OpenAI 兼容 API 接入点
- **那么** 调用方可以通过 planner factory 注入 `base_url` 与 `api_key`
- **那么** planner 使用该配置创建 Deep Agents 运行实例

#### 场景:factory 按统一优先级解析配置
- **当** 同一配置项同时存在调用参数、环境变量和默认值
- **那么** factory 必须按统一优先级解析（调用参数优先于环境变量，环境变量优先于默认值）
- **那么** planner 实例的运行配置可被稳定预测和复现

### 需求:planner 必须提供结构化三态输出
系统必须以 `ready`、`needs_human`、`blocked` 三态返回规划结果，禁止将可执行结果、澄清请求和系统故障折叠为单一自由文本响应。

#### 场景:信息充分时返回 ready
- **当** planner 已完成取证并生成合法任务文档
- **那么** 返回状态为 `ready`
- **那么** 返回体包含可执行 `task_document`

#### 场景:信息不足时返回 needs_human
- **当** planner 判断关键信息不足以安全生成任务文档
- **那么** 返回状态为 `needs_human`
- **那么** 返回体包含结构化澄清问题

#### 场景:系统阻塞时返回 blocked
- **当** 关键依赖不可用导致规划无法继续
- **那么** 返回状态为 `blocked`
- **那么** 返回体包含错误原因与恢复建议

### 需求:planner 必须先取证再触发 HITL
系统必须要求 planner 在触发 `needs_human` 之前优先尝试使用 `search` 与 `fetch_keys` 进行证据收集，禁止在可取证前提下直接向 DM 追问。

#### 场景:先工具取证后仍不确定
- **当** planner 完成至少一轮工具取证后仍存在关键歧义
- **那么** planner 触发 `needs_human`
- **那么** 问题内容基于已检索证据形成

### 需求:planner 必须执行双层校验闭环
系统必须对 planner 生成的任务文档先执行 Schema 结构校验，再执行执行器语义校验。若任一校验失败，planner 必须进入修复或澄清分支，禁止直接返回 `ready`。

#### 场景:Schema 失败触发修复
- **当** 任务文档缺少必需字段或字段类型错误
- **那么** planner 不得返回 `ready`
- **那么** planner 进入修复流程或转入 `needs_human`

#### 场景:语义校验失败触发修复
- **当** 任务文档引用未来步骤结果或使用非法 type/kind
- **那么** planner 不得返回 `ready`
- **那么** planner 基于错误信息修复或转入 `needs_human`

### 需求:planner 必须按固定优先级处理冲突证据
系统在 DM 意见、store 状态证据与 search 规则证据互相矛盾时，必须按固定优先级决策：`DM 意见 > store > search`。系统禁止在冲突场景下忽略该优先级并随机采信证据来源。

#### 场景:冲突证据按优先级收敛
- **当** planner 同时获得互相冲突的 DM、store 和 search 证据
- **那么** planner 优先采信 DM 意见
- **那么** 若缺少 DM 明确意见则按 `store > search` 顺序采信

## 修改需求

## 移除需求
