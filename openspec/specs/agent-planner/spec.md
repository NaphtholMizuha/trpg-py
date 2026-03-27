# agent-planner 规范

## 目的
定义 planner agent 的职责边界、信息获取流程、HITL 交互语义，以及输出 `TaskDocument` 的结构与校验闭环，确保 planner 在信息不完整场景下可解释、可恢复、可执行。
## 需求
### 需求:planner 必须驻留在 agent 命名空间并以结构化接口对外
系统必须在 `trpg_py.agent` 命名空间下提供 planner 能力，并以结构化输入输出接口供调用方使用，禁止仅通过临时 prompt 或不可复用脚本触发规划流程。planner 的默认模型认证信息必须通过统一配置解析后的环境变量密钥获取，而不是要求调用方把密钥直接写入项目配置文件。

#### 场景:调用方以结构化方式发起规划
- **当** 调用方提交 DM 指令和规划上下文
- **那么** planner 通过稳定接口接收请求
- **那么** 调用方无需了解内部工具编排细节
- **那么** 调用方无需在统一配置文件中直接保存真实模型密钥

### 需求:planner 默认配置必须通过 api_key_env 获取模型密钥
系统必须让 planner 的统一配置默认通过 `api_key_env` 获取模型 API key，禁止要求调用方在项目配置文件中直接写入 planner 密钥。

#### 场景:planner 从统一配置读取默认密钥
- **当** 调用方通过统一配置创建 planner 且未显式传入 `api_key`
- **那么** planner 必须使用配置加载层解析后的环境变量密钥
- **那么** 调用方无需在配置文件中直接保存真实密钥

### 需求:planner 必须以 TaskDocument 作为唯一执行目标
planner 必须以生成可被执行器消费的 `TaskDocument` 为目标产物，并且该文档必须满足当前执行器的结构约束（`task_id`、`version`、`policy`、`context`、`steps` 以及步骤级 `id/type/kind/args` 等字段语义）。

#### 场景:planner 产出可执行任务文档
- **当** planner 判断信息充分
- **那么** 输出中包含完整 `TaskDocument`
- **那么** 该文档可直接进入执行器校验与执行流程

### 需求:planner 必须通过 search 和 fetch_keys 获取证据
planner 必须将 `search` 与 `fetch_keys` 作为基础信息工具，并通过工具调用结果驱动后续推理分支。planner 禁止在可调用工具前提下跳过取证直接凭空生成关键规则结论或关键路径引用。对于候选 `TaskDocument` 的合法性收口，planner 必须能够进一步使用 `lint` 工具执行只读自检，但 `lint` 不得替代 `search` 与 `fetch_keys` 的取证职责。

#### 场景:planner 使用 search 补充规则证据
- **当** DM 指令涉及规则判断（如攻击、豁免、伤害）
- **那么** planner 可以调用 `search` 检索规则原文
- **那么** 规则结论建立在检索证据之上

#### 场景:planner 使用 fetch_keys 补充状态路径证据
- **当** planner 需要引用状态路径生成步骤参数
- **那么** planner 可以调用 `fetch_keys` 枚举候选路径
- **那么** 产出的路径引用与 state 点路径语义保持一致

#### 场景:planner 使用 lint 收口候选文档
- **当** planner 已具备足够规则证据和状态路径证据并准备返回 `ready`
- **那么** planner 可以调用 `lint` 对候选 `TaskDocument` 做只读合法性校验
- **那么** `lint` 的结果只用于校验候选文档，不得被当作规则证据或状态事实来源

### 需求:planner 必须显式区分 ready、needs_human 与 blocked
planner 必须以稳定状态语义区分三类规划结果：可直接执行、需要 DM 澄清、以及系统阻塞。系统禁止把这三类情况折叠为单一自由文本回复。对于 `needs_human` 与 `blocked`，系统还必须暴露可读的根因解释，禁止把内部校验失败或修复未收敛笼统伪装成“用户信息不足”。

#### 场景:信息充分时返回 ready
- **当** planner 已获得足够证据并完成文档校验
- **那么** 返回 `status=ready`
- **那么** 返回体包含 `task_document`

#### 场景:信息不足时返回 needs_human
- **当** planner 判断关键信息不足或不确定性过高
- **那么** 返回 `status=needs_human`
- **那么** 返回体包含结构化澄清问题列表
- **那么** 返回体包含说明当前缺口为何阻止生成稳定文档的解释

#### 场景:系统故障时返回 blocked
- **当** 工具调用连续失败或依赖不可用导致无法规划
- **那么** 返回 `status=blocked`
- **那么** 返回体包含可读错误原因与恢复建议

#### 场景:内部文档校验失败时暴露真实根因
- **当** planner 生成了结构合法但未通过执行器语义校验的 `TaskDocument` 且修复未收敛
- **那么** 系统不得仅返回泛化的“请补充关键细节”作为唯一解释
- **那么** 返回体或调试负载中必须可见最后一次校验失败原因
- **那么** 调用方可以区分这是内部产物失败而非纯业务信息缺失

### 需求:planner 必须支持 LLM 主导的不确定性判定并保留最小硬约束
系统必须允许 planner 由 LLM 主导判断“信息是否足够”，并在不确定时主动触发 HITL。与此同时，系统必须保留最小硬约束用于兜底，例如文档结构非法、关键实体不可唯一映射或关键工具错误等不可忽略风险。

#### 场景:LLM 识别语义不确定并触发澄清
- **当** 同一指令可映射到多个合法目标且证据不足以唯一决策
- **那么** planner 主动触发 `needs_human`
- **那么** 澄清问题聚焦最小必要决策点

#### 场景:命中硬约束时禁止强行输出 ready
- **当** 规划结果违反执行器必需结构或关键依赖不可用
- **那么** planner 不得返回 `status=ready`
- **那么** planner 必须转为 `needs_human` 或 `blocked`

### 需求:planner 输出必须包含可解释的缺口与假设信息
planner 在 `needs_human` 或存在推断前提时，必须返回结构化 `missing_info` 和 `assumptions` 等解释字段，禁止只返回不可审计的最终结论。若根因来自内部修复或文档校验失败，系统必须额外提供与该内部失败对应的解释字段或调试信息，而不能把 `missing_info` 退化为对用户无意义的占位值。

#### 场景:planner 返回澄清上下文
- **当** planner 需要 DM 补充法术环位或目标选择
- **那么** 返回体列出对应 `missing_info`
- **那么** 返回体说明若不澄清将导致的决策分歧

#### 场景:planner 返回内部失败上下文
- **当** planner 最终未能产出合法 `TaskDocument`
- **那么** 返回体必须保留与该失败对应的可读错误信息或解释字段
- **那么** smoke 脚本可以直接复用该信息生成默认失败摘要

### 需求:planner 必须采用 schema 约束与执行器校验的双层闭环
系统必须对 planner 生成结果同时应用 JSON Schema 结构约束与执行器语义校验。系统不得仅依赖 prompt 约定保证产物合法性。

#### 场景:Schema 拦截基础结构错误
- **当** planner 初稿缺失顶层字段或步骤关键字段
- **那么** Schema 校验先拒绝该产物
- **那么** planner 进入修复流程

#### 场景:执行器校验拦截语义错误
- **当** planner 产物通过 Schema 但引用未来步骤结果
- **那么** 执行器校验拒绝该产物
- **那么** planner 根据错误原因重试修复或触发 HITL

### 需求:planner 必须在提问前优先完成可用工具取证
系统必须要求 planner 在触发 HITL 之前尽可能完成 `search` 和 `fetch_keys` 的取证尝试，避免因未检索或未枚举路径造成过早提问。

#### 场景:先取证后提问
- **当** DM 指令初看存在歧义
- **当** 工具取证后仍无法收敛到单一可执行方案
- **那么** planner 才触发 `needs_human`
- **那么** 提问内容基于已获取证据而非泛化追问

### 需求:planner 必须保持与执行器的职责分离
planner 只负责“规划与文档生成”，不得在 planner 层直接提交状态写入或替代引擎执行步骤。规则结算结果必须由执行器基于 `TaskDocument` 在运行时产生。

#### 场景:planner 生成但不执行
- **当** planner 返回 `status=ready`
- **那么** 返回体仅包含待执行文档与规划元信息
- **那么** 实际状态变化仍由执行器负责提交

### 需求:系统必须允许后续扩展 reads 类值读取工具而不破坏 planner 契约
系统必须允许 planner 后续集成值读取类工具（如 `reads`）以降低 HITL 频率，但该扩展不得破坏既有 `ready/needs_human/blocked` 返回语义与校验闭环。

#### 场景:后续接入 reads 工具
- **当** planner 新增值读取工具用于补充证据
- **那么** 现有规划状态语义和输出契约保持兼容
- **那么** 既有调用方无需改动核心消费流程

### 需求:planner factory 必须从统一项目配置读取默认运行参数
系统必须要求 planner factory 的默认模型、接入点、超时、重试次数、规划轮数、工具预算以及默认 prompt 资源定位来自统一项目配置，而禁止继续以模块内 `DEFAULT_*` 常量、内嵌 prompt 字符串或独立路径约定作为长期配置来源。

#### 场景:planner factory 使用统一配置创建实例
- **当** 调用方未显式覆写 planner factory 的运行参数
- **那么** planner factory 从统一项目配置读取默认值
- **那么** planner 实例的运行行为与项目配置文件保持一致

#### 场景:planner factory 从统一配置读取 prompt 来源
- **当** 调用方通过统一配置创建 planner
- **那么** factory 必须从统一配置解析默认 prompt 目录与模板文件
- **那么** 最终创建出的 planner 使用该配置指定的 prompt 模板

### 需求:planner 必须通过统一配置入口消费配置
系统必须要求 planner 通过集中配置模块获取运行配置，而禁止在 planner 模块内部直接读取环境变量或散落的默认常量来形成项目级运行配置。

#### 场景:planner 模块不直接解析环境变量
- **当** planner 需要获取模型接入参数或运行参数
- **那么** planner 通过统一配置入口读取对应字段
- **那么** planner 模块不再自行维护独立环境变量解析路径

### 需求:planner 必须提供可手动运行的集成测试脚本
系统必须提供一个位于 `smoke/test_planner.py` 的可手动运行脚本，用于让开发者直接观察 planner 的结构化效果，禁止要求开发者只能通过单元测试或临时代码片段验证 planner 行为。该脚本必须以真实 planner 配置链路和真实工具链路作为默认运行路径，而不是以内置 fake 响应模拟结果。

#### 场景:开发者手动运行 planner 集成脚本
- **当** 开发者执行 `smoke/test_planner.py` 并提供 DM 指令或示例场景
- **那么** 脚本调用 `trpg_py.agent` 暴露的 planner 能力发起一次真实规划
- **那么** 规划过程使用真实 `search` 与真实 `fetch_keys`
- **那么** 输出中展示真实返回的 `ready`、`needs_human` 或 `blocked` 等结构化状态

### 需求:planner 集成脚本必须帮助开发者观察代表性规划结果
系统必须让 planner 集成脚本支持至少一个可复现示例场景，并能够向开发者清晰展示 `task_document`、澄清问题或阻塞原因等核心结果。该结果必须来源于真实调用，而不是脚本预制的假响应。默认示例场景必须使用一份足够丰富的 world state 文件，而不是继续使用只含少量字段的内联最小 state。

#### 场景:脚本展示 planner 结果摘要
- **当** planner 集成脚本完成一次规划请求
- **那么** 调用方可以从输出中看出 planner 返回的真实状态类型
- **那么** 调用方可以查看对应的真实 `task_document`、`questions` 或 `error` 摘要

#### 场景:脚本使用更真实的默认世界状态
- **当** 开发者直接运行 `smoke/test_planner.py`
- **那么** 脚本必须从配置指定的默认 world state 文件加载示例状态
- **那么** 该状态必须覆盖比当前极简内联 state 更完整的角色、战斗或环境信息
- **那么** 脚本不得继续把内联最小字典作为默认真相

### 需求:planner smoke 脚本必须默认验证真实配置链路
系统必须让 `smoke/test_planner.py` 默认读取项目统一配置并构造真实 planner，禁止以内置 fake agent、fake LLM、fake tool 或脚本预制结果作为默认 smoke 路径。默认 smoke 状态也必须通过配置指定的 world state 文件提供，并在加载后转换为真实 planner 使用的 state 结构。

#### 场景:开发者直接运行 planner smoke 脚本
- **当** 开发者执行 `python smoke/test_planner.py`
- **那么** 脚本必须读取 `config/config.toml` 或显式传入的配置路径
- **那么** 脚本必须通过 `trpg_py.agent.create_planner(...)` 构造真实 planner
- **那么** 规划过程中必须使用真实 `search` 与真实 `fetch_keys` 工具链路
- **那么** 默认 state 必须来自配置指定的 world state 文件而不是内联常量
- **那么** 脚本不得默认返回脚本内部伪造的规划结果

### 需求:planner smoke 脚本必须展示真实规划结果
系统必须让 `smoke/test_planner.py` 的输出直接来源于真实 planner 调用结果，禁止把预制 `ready`、`needs_human` 或 `blocked` 响应当作 smoke 输出真相。对于 `needs_human` 中由内部 `TaskDocument` 校验失败触发的场景，默认人类可读摘要也必须展示具体失败原因，禁止只剩泛化问题和抽象 reason。

#### 场景:脚本输出真实 planner 结果
- **当** planner smoke 脚本完成一次规划调用
- **那么** 人类可读摘要或 JSON 输出必须展示真实返回的 `status`
- **那么** 若返回 `ready`，输出中必须可见真实 `task_document` 摘要或正文
- **那么** 若返回 `needs_human` 或 `blocked`，输出中必须可见真实问题列表或错误信息

#### 场景:默认摘要展示内部文档失败原因
- **当** planner smoke 脚本返回 `status=needs_human` 且 `reason=task_document_validation`
- **那么** 非 `--debug` 的默认人类可读输出必须展示最后一次文档校验失败原因
- **那么** 调用方无需切换到 JSON 或 `--debug` 才能知道该产物为何不是合法 `TaskDocument`

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

### 需求:planner 依赖的工具调用必须可通过运行期日志观察
系统必须确保 planner 所依赖的工具调用在运行期可观察，禁止让调用方只能依赖最终 `ready/needs_human/blocked` 结果反推中间工具输入输出。

#### 场景:planner 调用 search 或 fetch_keys 时留下工具日志
- **当** planner 在一次规划过程中调用 `search` 或 `fetch_keys`
- **那么** 运行期日志中必须可见该工具调用的输入参数摘要
- **那么** 运行期日志中必须可见该工具调用的输出状态或错误结果
- **那么** 调用方无需修改 planner 业务逻辑即可观察这些日志

### 需求:planner 必须能够使用 reads 补充状态值证据
系统必须允许 planner 在已知或可发现候选路径的前提下使用 `reads` 工具读取当前状态值，以确认实体 ID、AC、资源或其他关键参数，禁止在 state 已经包含答案时仅因无法读取值而直接进入 HITL。

#### 场景:planner 通过 reads 确认目标实体与关键数值
- **当** planner 已通过 `fetch_keys` 找到候选状态路径但仍需确认具体值
- **那么** planner 可以调用 `reads` 读取这些路径上的当前值
- **那么** planner 可以根据读取结果确认 actor_id、target_id 或其他关键任务参数
- **那么** 若读取结果已足够支撑规划，planner 不得仅因“未人工澄清”而进入 `needs_human`

### 需求:planner 必须从外置文本模板加载 prompt
planner 必须从统一配置指定的外置文本模板加载 system prompt 和 user prompt，禁止继续把长期默认 prompt 文案内嵌在 `planner.py` 中作为唯一真相。

#### 场景:planner 使用配置指定的默认 prompt 模板
- **当** 调用方通过统一配置创建 planner 且未显式覆写 prompt 来源
- **那么** planner 必须从配置指定的文本模板加载 system prompt 和 user prompt
- **那么** planner 不得继续依赖代码内联 prompt 字符串作为默认行为

### 需求:planner 必须渲染受控占位符并对模板错误快速失败
planner 必须支持把 instruction、context、policy、tool budget 和 repair feedback 等动态字段渲染到外置 prompt 模板中，并在模板文件缺失、不可读、占位符未知或渲染后仍残留未解析占位符时快速失败。

#### 场景:planner 渲染 user prompt 动态内容
- **当** planner 发起一次新的规划请求
- **那么** user prompt 模板必须能接收 instruction、context JSON、policy JSON 和 tool budget 等动态内容
- **那么** 首轮或修复轮的最终 prompt 必须来源于模板渲染结果

#### 场景:planner 在修复轮渲染 validation feedback
- **当** planner 因 schema 或语义校验失败进入修复轮
- **那么** 系统必须把 validation feedback 注入外置 user prompt 模板
- **那么** 修复轮不必回退到代码内嵌字符串拼接

#### 场景:prompt 模板装载或渲染失败
- **当** planner 配置引用了不存在的 prompt 文件、不可读文件或非法占位符
- **那么** planner 创建或调用必须快速失败
- **那么** 错误信息必须指出具体的 prompt 文件或模板问题

### 需求:planner smoke 调试入口必须暴露规划轨迹摘要
系统必须让 planner 的手动 smoke/debug 入口在显式调试模式下展示本次规划的关键轨迹，禁止只输出最终三态而完全隐藏中间修复与失败上下文。

#### 场景:开发者以调试模式运行 planner smoke 脚本
- **当** 开发者以 planner smoke/debug 入口运行一次真实规划并显式开启 debug
- **那么** 输出中必须包含规划轮次摘要
- **那么** 输出中必须包含每轮结构化响应或其可读摘要
- **那么** 若发生修复，输出中必须包含修复反馈或最后一次校验失败原因

#### 场景:开发者以 JSON 形式查看调试结果
- **当** 开发者以 JSON 模式运行 planner smoke/debug 入口并显式开启 debug
- **那么** 返回体必须包含结构化的 debug 负载
- **那么** 该负载必须可用于自动测试断言或人工复制排查

### 需求:planner smoke 脚本必须从正常嵌套 TOML 载入默认 world state
系统必须让 `smoke/test_planner.py` 在读取默认 world state 文件时直接消费正常嵌套 TOML 结构，禁止继续要求默认 fixture 以扁平点路径键格式书写。

#### 场景:planner smoke 读取默认 world state
- **当** 开发者运行 `smoke/test_planner.py` 且默认 state 来源为 `config/world_state.toml`
- **那么** 脚本可以直接从嵌套 TOML 解析结果构造 planner 使用的 state
- **那么** 脚本不再依赖“顶层 TOML key 本身是点路径”这一特殊约定

### 需求:planner prompt 必须显式教授 TaskDocument DSL
系统必须让 planner 使用的提示词显式描述合法 `TaskDocument` 的最小结构、允许的步骤 `type/kind` 组合、引用约定和至少一个代表性规范示例，禁止仅以“生成 TaskDocument”之类的抽象描述要求模型自行猜测 DSL。

#### 场景:planner 根据显式 DSL 约束规划攻击动作
- **当** planner 处理类似“哥布林攻击 hero_1”的 DM 指令
- **那么** prompt 中必须向模型暴露 `task_id`、`version`、`context`、`policy`、`steps` 以及步骤级 `id/type/kind/args` 等最小骨架
- **那么** prompt 中必须明确合法步骤类型与引用方式，而不是允许模型自由发明 `action`、`actor` 等替代字段
- **那么** prompt 中必须提供至少一个符合当前引擎 DSL 的规范示例

### 需求:planner 在返回 ready 前必须能够使用 lint 做候选文档自检
系统必须允许 planner 在准备返回 `status=ready` 前将候选 `TaskDocument` 提交给 `lint` 工具做只读校验，并根据结构化校验结果修复或降级，而禁止把所有合法性发现都推迟到最终兜底校验之后。

#### 场景:planner 用 lint 收口候选任务文档
- **当** planner 已完成规则与状态路径取证并生成候选 `TaskDocument`
- **那么** planner 必须能够调用 `lint` 对该候选文档执行只读校验
- **那么** 若 `lint` 返回非法结果，planner 必须根据错误结果修复文档或转入 `needs_human/blocked`
- **那么** 若 `lint` 返回合法结果，planner 才可以继续进入最终 `ready` 输出流程

### 需求:planner prompt 必须显式保留 DnD5e 攻击中的 nat 标签语义
系统必须让 planner 默认 prompt 在 DnD5e 攻击规划语境下显式指导模型为 `check.attack` 保留 `tags=["nat"]` 或等价的天然骰追踪语义。系统禁止继续让模型仅生成“可命中判定”的最小攻击检定步骤，却遗漏天然 20 / 天然 1 对攻击结果的规则语义。

#### 场景:planner 规划一次 DnD5e 武器攻击
- **当** planner 需要把一次近战或远程武器攻击规划为 `check.attack`
- **那么** prompt 必须明确提示攻击检定默认保留 `nat` 标签语义
- **那么** prompt 中的攻击模式或 canonical example 必须出现带 `tags=["nat"]` 的 `check.attack`
- **那么** 模型不会把天然 20 退化为普通 `success`

### 需求:planner prompt 必须显式传播攻击暴击到 damage.apply
系统必须让 planner 默认 prompt 在攻击后续包含 `damage.apply` 时，显式指导模型把前序攻击步骤的 `crit_success` 结果传播为伤害步骤的 `is_critical` 输入。系统禁止继续让 prompt 只要求“命中后造成伤害”，却遗漏暴击扩骰所需的显式链路。

#### 场景:planner 规划一次攻击命中后的伤害步骤
- **当** planner 为一次 `check.attack` 生成后续 `damage.apply`
- **那么** prompt 必须明确提示该伤害步骤在命中时执行，并在暴击时设置 `is_critical`
- **那么** prompt 中的示例必须展示从 `result.<attack-step>.outcome == crit_success` 到 `is_critical` 的映射
- **那么** 模型可以生成保留 DnD5e 暴击扩骰语义的伤害步骤

### 需求:planner prompt 必须显式区分工具路径与 TaskDocument 引用路径
系统必须让 planner 默认 prompt 明确区分两套路径语义：`fetch_keys` 与 `reads` 消费的是当前 store 的裸点路径（如 `actors.aldera.ac`），而最终 `TaskDocument` 中的 `$ref` 使用 `state.*`、`context.*`、`result.*` 命名空间。系统禁止继续让 prompt 把这两类路径语法混为一谈，导致模型把 `state.` 前缀误用于工具参数。

#### 场景:planner 使用 fetch_keys 和 reads 时采用裸 store 路径
- **当** planner 需要发现 actor、AC、HP、攻击加值或其他 state 路径
- **那么** prompt 必须告诉模型向 `fetch_keys` 与 `reads` 传入裸 store 路径
- **那么** 路径示例必须使用 `actors.goblin_1.ac`、`actors.aldera.hp` 等形式
- **那么** prompt 不得把 `state.actors...` 当作工具参数示例

#### 场景:planner 在 TaskDocument 中继续使用命名空间引用
- **当** planner 已经通过工具确认了真实 store 路径并准备输出 `TaskDocument`
- **那么** prompt 必须告诉模型在 `$ref` 中使用 `state.<store-path>` 形式引用 state
- **那么** prompt 必须保留 `context.*`、`state.*`、`result.*` 等命名空间引用约定
- **那么** 模型可以区分“工具输入路径”和“最终文档引用路径”不是同一种字符串

#### 场景:prompt 示例展示从工具路径到最终引用的映射关系
- **当** prompt 提供 canonical example、工具说明或路径示例
- **那么** 相邻内容中必须可见从 `actors...` 裸路径到 `state.actors...` 引用路径的对应关系
- **那么** 开发者和模型都可以看出 planner 应先用工具确认真实路径，再把该路径写入最终 `$ref`
