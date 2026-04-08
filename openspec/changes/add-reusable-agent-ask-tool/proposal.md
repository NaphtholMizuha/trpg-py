## 为什么

现在 Context Agent 在背景未明晰时只能返回 `needs_human` 或 `blocked`，但缺少一个正式的、可复用的 `ask` tool 来把不确定点组织成面向 DM 的确认请求。这会让“需要人来定”的信息无法作为一等结构化结果暴露出来，既不利于交互，也不利于以后把同类能力装载到其他 agent 上。

现在需要把“向 DM 发起澄清确认”升级成一个一等工具：它先服务 Context Agent，但工具本身必须是 agent-agnostic 的长期能力，支持候选选项、默认值和自定义输入，以便后续其他 agent 也能复用同一交互协议。

## 变更内容

- 为 agent runtime 新增一个可复用的 `ask` tool，用于在背景未明晰、但仍可组织成明确确认请求时向 DM 发起询问。
- 要求 `ask` tool 的问题模型至少支持：预设选项、推荐/默认选项、以及允许 DM 提供自定义输入。
- 修改 Context Agent 的缺口处理规则：当存在可明确提问的歧义或缺失时，优先构造 `ask_requests`，而不是继续依赖 `unresolved_gaps` 作为面向 DM 的主返回承载。
- 明确 `ask` tool 不是 Context Agent 私有工具，而是后续可装载到其他 agent 上的通用交互能力。
- 本次实现范围先落在 Python CLI，但 ask 的数据契约必须保持宿主无关，避免以后接入 HTTP 接口时重做 agent 侧协议。
- 调整相关 prompt / skill / eval 约束，使主 agent 与 Context Agent 知道何时应调用 `ask`，以及如何展示候选项、默认值和自定义输入入口。

## 功能 (Capabilities)

### 新增功能
- `agent-ask-tool`: 定义一个可复用的 agent 问询工具，用于向 DM 发起带选项、默认值和自定义输入入口的结构化确认请求。

### 修改功能
- `delegating-agent-runtime`: 扩展 agent runtime 的默认工具装配与委派结果，使子 agent 可以发出结构化 `ask_requests`，而不再把面向 DM 的缺口停留在自由文本返回里。
- `agent-planner`: 更新 planner 对外能力，允许规划链路在需要 DM 澄清时暴露结构化 `ask` 请求。
- `planner-node-prompts`: 更新主 agent / Context Agent 的提示约束，使其学会在适合的歧义场景中调用 `ask`，而不是只输出模糊问题文本。

## 影响

- 受影响代码主要包括 `src/augury/agent/runtime.py`、`src/augury/agent/subagents/context_agent.py`、工具装配层、eval 脚本以及相关测试。
- 需要新增一套可复用的 ask-tool 数据契约，供 Context Agent 先使用，并保留给其他 agent 的扩展空间。
- 本次交付只要求提供 Python CLI 侧的 ask 展示与回填方式；HTTP 等其他宿主暂不实现，但不得把协议设计成 CLI 私有格式。
- 主 agent 与 Context Agent 的 prompt / skill 约束将新增“何时 ask、如何给选项、默认值和自定义输入”的长期规范。
