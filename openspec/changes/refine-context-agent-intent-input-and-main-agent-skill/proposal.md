## 为什么

当前项目虽然已经有了主 agent 到 Context Agent 的委派链路，但这条链路的输入仍然更像“把用户 instruction 和部分运行态材料直接塞给子 agent”，而不是“主 agent 明确发布一项事实获取任务”。这会让 Context Agent 的职责边界、eval 脚本的观察面，以及主 agent 应该如何构造委派输入都显得偏松散。

现在需要把这条接口收紧成更符合委派心智的形状：主 agent 传给 Context Agent 的输入应围绕 `intent.goal.requests` 组织，其中 `requests` 是自然语言描述的事实获取请求；同时补强 eval 脚本的测试，并新增一条主 agent 使用 Context Agent 的 skill/prompt 约束，避免继续把这套行为隐藏在临时实现细节里。

## 变更内容

- **BREAKING** 将 Context Agent 的默认委派输入从以 `instruction`、`state`、`context` 为中心的结构，调整为以 `intent`、`goal`、`requests` 为中心的结构化输入。
- 要求 `requests` 表达为自然语言的事实获取请求，而不是问句列表、字段名列表或自由散文。
- 要求 Context Agent 默认通过自身工具获取规则和状态证据，而不是把 `state`、`context` 作为长期必备输入字段传递。
- 调整 Context Agent eval 脚本，使其默认展示新的 `intent.goal.requests` 输入，并补强自动测试以断言输入契约与输出 bundle 的对应关系。
- 新增一条主 agent 使用 Context Agent 的 skill / prompt 约束，要求主 agent 在委派前先把用户原始意图整理为明确的 `goal` 和自然语言事实请求，再调用 Context Agent。

## 功能 (Capabilities)

### 新增功能
- `main-agent-context-skill`: 定义主 agent 如何把用户意图整理成 `intent.goal.requests` 形式，并用它稳定委派 Context Agent。

### 修改功能
- `delegating-agent-runtime`: 调整主 agent 到 Context Agent 的默认委派输入契约，并明确 Context Agent 通过工具而不是输入 payload 自行获取状态与规则材料。
- `context-agent-eval-script`: 调整 eval 脚本输入形状与展示要求，并补强围绕新契约的测试要求。
- `agent-planner`: 补充 planner 对外接口中主 agent 如何构造 Context Agent 委派任务的规范级约束。
- `planner-node-prompts`: 调整主 agent 或等价指引，使其学会把用户意图整理成自然语言事实获取请求，而不是继续直接下发原始 instruction。

## 影响

- 受影响代码主要包括 `src/augury/agent/runtime.py`、`src/augury/agent/context_eval.py`、`src/eval/context_agent_eval.py`、相关测试，以及主 agent 使用的 prompt/skill 约束。
- Context Agent 的委派输入属于破坏性契约变更，现有 helper、eval 脚本和测试都需要同步调整。
- 主 agent 将拥有一条更明确的 Context Agent 使用规范，后续更容易继续扩展委派策略而不让 Context Agent 接口漂移。
