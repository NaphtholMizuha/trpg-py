## 为什么

现在的 `ask` 虽然名义上是 tool，但它实际返回的是 `AskRequest`，Context Agent 调用之后并不能拿到工具结果继续生成最终 `ContextBundle`。这会让 `ask` 更像 request emitter，而不像真正的工具调用，也让“agent 带着 ask 结果继续跑”的心智和实际实现发生偏离。

现在需要把 `ask` 升级成可中断、可恢复的工具：底层运行时以 interrupt/resume 语义暂停并恢复 agent，CLI 调试宿主则可以把这套过程表现成同步问答，让 Context Agent 在 ask 之后继续产出更新后的结果。

## 变更内容

- 为 agent runtime 引入可中断工具的运行时语义，使 `ask` 可以在工具内部触发 interrupt，而不是只把请求对象抛给外层。
- 将 `ask` tool 从“返回 `AskRequest`”升级为“在恢复后返回 `AskResponse`”，让 Context Agent 能带着工具结果继续执行。
- 明确底层真相是异步 interrupt/resume，而 Python CLI 可以提供同步外观；系统禁止为了 CLI 方便重新引入显式的人类节点图。
- 修改 Context Agent 的 ask 行为：当缺少 DM 决定时，允许通过可中断 ask 暂停，并在恢复后继续补全证据和最终 `ContextBundle`。
- 调整 eval 与 planner 结果约束，使其能观察 pending interrupt、恢复输入和恢复后的最终结果，但不要求在本次变更中同时完成所有 HTTP 宿主接入。

## 功能 (Capabilities)

### 新增功能
- `interruptible-agent-tools`: 定义 agent runtime 对可中断工具的统一运行时语义，包括 interrupt、resume 和宿主适配边界。

### 修改功能
- `agent-ask-tool`: 将 ask 从请求构造工具升级为可中断工具，要求其恢复后向 agent 返回结构化回答结果。
- `agent-planner`: 更新 planner / Context Agent 行为，使 ask 之后可以继续生成结果，而不是停在 ask 请求输出上。
- `context-agent-eval-script`: 更新 eval 脚本的定位，使其既能观察 ask 中断，也能在 CLI 宿主中完成恢复并展示恢复后的最终 bundle。

## 影响

- 受影响代码将包括 `src/augury/agent/runtime.py`、`src/augury/agent/tools/ask.py`、`src/augury/agent/subagents/context_agent.py`、CLI ask adapter、eval runner 和相关测试。
- 需要新增一套运行时级别的 interrupt/resume 协议，并明确哪些结果属于 pending interrupt、哪些属于恢复后的 tool result。
- Python CLI 仍是当前唯一需要落地的宿主，但其同步体验必须建立在统一 interruptible tool 契约之上。
- 这次变更会影响现有 ask / eval 的控制流语义，属于重要行为升级，但不要求重新引入显式节点图工作流。
