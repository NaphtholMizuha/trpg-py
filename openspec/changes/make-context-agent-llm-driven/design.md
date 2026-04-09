## 上下文

当前运行时虽然在 `config/config.toml` 中声明了 `planner.model`、`planner.context_agent_prompt`，也提供了 `config/prompts/planner_context_agent_system.txt` 与 `planner_context_agent_user.txt`，但 `ContextAgent.run()` 实际仍然完全走本地 Python 逻辑：先调用 `_analyze_intent()` 做动作识别与实体匹配，再通过 `_next_clarification_request()` 等硬编码分支决定 ask，最后调用 `grep/search` 收集证据。

这意味着现在的 Context Agent 只是“带有工具的启发式分析器”，而不是“由模型驱动的子 agent”。prompt 文件没有接线，planner 模型配置也没有进入这条链路，因此：

- 调 prompt 无法改变真实行为；
- ask 触发条件被写死在 `ContextAgent` 类内部逻辑里；
- eval 与测试难以反映未来真正想要的 LLM 行为；
- 代码里同时存在“规范要求模型决定 ask”和“实现仍由类内部硬编码”的偏差。

这次设计的目标不是让模型直接执行工具调用副作用，而是把这些职责明确收敛到 `ContextAgent` 自身：它负责准备 prompt 输入、执行模型请求、解析结构化动作、调用自己装配的 `grep/search/ask` 工具、校验输出并组装 `ContextBundle`。真正的“下一步做什么”由模型根据 prompt 和中间证据决定。

同时，这里的“LLM 驱动”不是指在 `ContextAgent.run()` 里再手写一套临时模型 while-loop。结合仓库现有长期约束，Context Agent 最基础的执行体也应当是 `langchain.create_agent` 产出的 agent；外围 Python 代码负责装配 tools、prompt、结构化响应约束和结果适配，而不是重新发明一套平行的 agent runtime。

## 目标 / 非目标

**目标：**

- 让 `ContextAgent` 真实使用统一配置中的 planner 模型与 context-agent prompt。
- 用模型驱动的多轮决策替换当前 `_analyze_intent` + 硬编码 ask 触发流程。
- 保留现有 `grep/search/ask` 工具边界和 `ContextBundle` 结构化输出契约。
- 提供可注入的模型客户端/适配层，使单测与 focused eval 能稳定验证 LLM 驱动流程。
- 明确模型调用失败、结构化输出不合法、工具报错时的降级和错误语义。

**非目标：**

- 本次不把 `ResolutionAgent` 一并改造成 LLM 驱动。
- 本次不引入任意开放工具调用协议或让模型直接拥有未经 `ContextAgent` 校验的执行权限。
- 本次不重做 `ContextBundle` 的整体 schema，只在必要处补充 LLM 驱动所需字段或注释。
- 本次不要求落地新的外部配置节；优先复用已有 `planner` 模型与 prompt 配置。

## 决策

### 决策 1：新增受配置驱动的 Context Agent 模型适配层

`PlannerAgent` 在装配 `ContextAgent` 时应同时注入一个模型调用依赖，该依赖复用现有 `planner.model`、`base_url`、`api_key`、`timeout`、`max_retries` 配置，并向 `ContextAgent` 暴露一个窄接口，例如“给定 system prompt、user prompt、历史 scratchpad，返回结构化动作”。

选择理由：

- 复用现有 planner 模型配置，避免再引入第二套 context-agent 专属密钥或模型真相。
- 让 `ContextAgent` 可以在测试中替换为 fake client，而不是直接依赖真实 SDK。
- 把模型供应商差异限制在一处，避免 `context_agent.py` 与具体 API 形态耦合。

备选方案：

- 直接在 `ContextAgent` 内部 new OpenAI client。未采用，因为会把配置解析、重试和测试替身分散到子 agent 内部。
- 继续只用本地启发式逻辑。未采用，因为这正是本次要移除的限制。

### 决策 2：Context Agent 的核心执行体必须由 `langchain.create_agent` 驱动

`ContextAgent` 的 LLM 推理主路径必须由 `langchain.create_agent` 产出的 agent 承担。`ContextAgent` 类本身负责：

- 装配 `grep/search/ask` 工具；
- 加载和渲染 context-agent prompt；
- 向 `create_agent` 提供模型、tools 和结构化响应约束；
- 将 agent 产出的结构化结果适配为现有 `ContextBundle`。

选择理由：

- 这与仓库现有 task/dsl 节点的长期架构真相一致，不会让 Context Agent 变成一个特立独行的手写 runtime。
- `create_agent` 天然适合承载“模型 + tools + prompt”的 agent 执行边界。
- 后续如果 delegating runtime 还要新增更多 LLM 子 agent，可以复用同一套 agent runtime 心智。

备选方案：

- 在 `ContextAgent.run()` 中手写模型循环。未采用，因为这会复制一套平行的 agent runtime，并增加维护成本。
- 继续维持纯启发式实现。未采用，因为无法满足 LLM 驱动目标。

### 决策 3：Context Agent 通过 `create_agent` 驱动多轮取证与 ask/final 输出

`ContextAgent.run()` 应围绕 `create_agent` 驱动的多轮执行来组织。agent 每轮只能产出两类受限结构化动作之一：

- `collect_evidence`: 通过 `create_agent` 调用自己装配的 `grep` 或 `search`
- `ask_or_finish`: 返回 `ask_request`、`ready bundle` 或 `blocked bundle`

`ContextAgent` 负责：

- 渲染 prompt，提供 `intent/goal/requests`、当前证据摘要、历史 ask responses；
- 为 agent 的结构化输出提供 schema 并校验结果是否合法；
- 让 agent 只看到自己持有的 `grep/search/ask` 工具，并把工具结果追加到后续轮次上下文；
- 在达到轮次上限或模型输出不合法时返回结构化错误/阻塞结果。

选择理由：

- 保留工具执行权在 `ContextAgent` 自身，避免模型越权。
- 允许模型基于中间证据改变策略，而不是一次性硬编码 ask。
- 便于在测试里断言每轮模型动作与工具调用序列。

备选方案：

- 一次模型调用直接产出最终 `ContextBundle`。未采用，因为这样无法支持“先取证再 ask”的多步过程。
- 让模型直接返回自由文本计划再由 `ContextAgent` 侧正则解析。未采用，因为太脆弱，且难以稳定测试。

### 决策 4：将现有 prompt 文件升级为真实运行时模板

运行时必须真实读取并渲染 `planner_context_agent_system.txt` 与 `planner_context_agent_user.txt`。user prompt 至少需要注入：

- `intent`
- `goal`
- `requests`
- 当前已收集的规则证据与状态证据摘要
- 已有 ask responses
- 可用工具说明与允许输出的结构化动作格式

选择理由：

- 让 prompt 文件成为可调优、可测试、可评审的长期真相。
- 避免“配置里有 prompt，实际代码完全没用”的漂移继续扩大。

备选方案：

- 仍在代码里内联 context-agent prompt。未采用，因为仓库已经建立了 prompt 文件与配置惯例。

### 决策 5：保留本地启发式逻辑作为窄范围兼容辅助，而不是主真相

现有 `_collect_entities()`、部分目标片段提取、证据整理辅助函数可以按需保留，用于：

- 把 state 预处理为更适合模型消费的候选摘要；
- 在模型要求 `grep` 时构造更稳健的默认表达式；
- 为测试比较提供稳定的 bundle 组装逻辑。

但 `_analyze_intent()` 及 `_next_clarification_request()` 不再作为主决策真相；如果短期需要保底，只能作为显式 fallback，在模型不可用或输出非法时启用，并且必须在代码与测试中标明这是兼容路径。

选择理由：

- 复用已有无副作用帮助函数，减少不必要重写。
- 防止“为了接 LLM 而把所有本地辅助能力全部推倒重来”。

备选方案：

- 全量删除所有旧 helper。未采用，因为其中一部分仍然适合作为预处理或 bundle 组装工具。

### 决策 6：测试与 eval 通过 fake agent / fake model 精确覆盖三类主路径

测试基线需要覆盖至少三类行为：

- agent 先取证再返回 `ready`
- 模型直接返回结构化 `ask_request`
- 模型因证据不足或工具错误返回 `blocked/error`

focused eval 则需要显示：

- 当前渲染给 Context Agent 的 prompt 输入关键信息
- agent 每轮动作摘要
- 最终 bundle 或 ask interrupt 结果

选择理由：

- LLM 驱动的行为如果没有 fake agent 或 fake model 测试，很快会因为 prompt 漂移而失真。
- eval 需要能帮助维护者观察“模型是如何决定 ask/取证/结束”的。

## 风险 / 权衡

- [`create_agent` 输出结构化动作不稳定] → 通过受限 schema、`ContextAgent` 内部校验和 fake agent/fake model 测试收紧输出面。
- [引入真实模型调用后单测变脆弱或依赖网络] → 通过依赖注入和 fake client 保证默认测试不出网。
- [prompt 调整导致行为波动] → 在 focused eval 中暴露 prompt 输入与每轮动作，并增加回归测试覆盖关键案例。
- [旧启发式 fallback 长期反客为主] → 明确 fallback 仅用于模型错误场景，不能继续承担默认控制流。
- [多轮 agent loop 导致复杂度上升] → 通过有限轮次、固定动作类型和 `ContextAgent` 统一 scratchpad 控制复杂度。

## 迁移计划

1. 先补充和更新 OpenSpec 规范，明确 Context Agent 的长期真相是 LLM 驱动。
2. 增加 prompt 读取/渲染与模型适配层，并在 `PlannerAgent` 装配时注入 `ContextAgent`。
3. 用 `langchain.create_agent` 重构 Context Agent 的核心执行体，并保留现有 bundle schema 与工具边界。
4. 更新 focused eval、单测与测试夹具，默认使用 fake agent 或 fake model 验证主路径。
5. 视实现情况决定是否保留一个显式 fallback，并在日志/结果中清楚标注。

回滚策略：

- 若模型接线在实现阶段产生较大不确定性，可先在运行时保留启发式 fallback，但必须让 LLM 路径成为默认路径。
- 若 prompt 结构一时无法稳定，可先把动作 schema 和 loop 接通，再迭代 prompt 文案，而不是回退到类内部硬编码控制流。

## 开放问题

- 结构化动作是直接用 Pydantic JSON schema 约束，还是先用较薄的 dict schema 再校验。
- 现有 `planner.model` 是否足够同时承载 main agent 和 context agent，还是后续需要细分模型配置。
- 当模型多轮连续只请求低价值搜索时，是否需要加入最小证据收益或工具预算保护。
