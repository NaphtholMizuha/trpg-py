## 上下文

当前项目已经把 `ask` 命名成工具，并围绕它建立了统一的 `AskRequest` / `AskResponse` 契约，以及 Python CLI 的宿主适配层。但这套实现还有一个关键错位：`ask` 虽然叫 tool，运行时语义却更接近“构造一个待外层处理的请求对象”。Context Agent 调用它之后不会继续拿着工具结果生成最终 `ContextBundle`，而是停在 `ask_requests` 这一级。

这个错位会带来两层问题。第一，agent 作者的编程心智被破坏了：他们自然会认为“调用 ask 后应该带着回答继续跑”。第二，运行时语义也被分裂了：CLI 看起来像同步问答，但底层并没有统一的 interrupt/resume 模型，只是在 eval runner 外围做展示和采集。

你现在想要的不是重新回到显式节点图，也不是把系统拆成 `human_node` 之类的固定编排单元。你想要的是：agent 仍然以“工具调用”的方式写逻辑，但运行时允许某些工具触发中断；对 CLI 来说，这个中断可以表现成同步问答；对未来 HTTP 等宿主来说，它仍然保留异步恢复的长期边界。

## 目标 / 非目标

**目标：**
- 把 `ask` 升级成真正的可中断工具，而不是只返回请求对象的 request emitter。
- 为 agent runtime 定义统一的 interrupt/resume 语义，使工具可以触发挂起并在恢复后返回最终结果。
- 让 Context Agent 在 ask 之后继续生成结果，而不是停在 ask 请求输出上。
- 保持 agent 侧编程模型接近普通工具调用，同时把宿主差异下沉到 runtime / adapter。
- 让 Python CLI 在当前阶段表现成同步问答，但不污染底层异步恢复真相。

**非目标：**
- 本次不重新引入显式的人类节点图或固定 workflow graph。
- 本次不要求同时落地 HTTP / Web UI 宿主。
- 本次不把所有工具都做成可中断；当前重点只覆盖 ask，并为未来类似工具提供共用运行时能力。
- 本次不要求同时实现复杂的多轮会话编排、持久化恢复历史或跨进程恢复协议。

## 决策

### 决策 1：将 ask 定义为 interruptible tool，而不是普通请求构造工具

`ask` 的运行时语义将从：
- 输入问题参数
- 返回 `AskRequest`

升级为：
- 输入问题参数
- 若需要人类回答，则触发 interrupt
- 在 runtime 恢复后返回 `AskResponse`

对 agent 作者来说，`ask` 仍然表现为一个工具调用；但对 runtime 来说，它属于可中断工具，需要支持挂起与恢复。

选择理由：
- 这能让“ask-as-a-tool”与实际行为重新一致。
- 这让 Context Agent 可以真正拿到工具结果继续产出最终 bundle。
- 这比把 ask 继续放在外层 eval / runner 手工编排更像长期运行时能力。

备选方案：
- 继续保留 ask 只返回 `AskRequest`。未采用，因为这让 ask 不像真正工具，也迫使外层永远手动回填。
- 引入专用 human node。未采用，因为这会把架构重新拉回显式节点编排。

### 决策 2：底层采用异步 interrupt/resume 语义，CLI 只提供同步 facade

运行时真相是：
- 工具调用可能返回 pending interrupt
- runtime 保存挂起上下文
- 宿主提供恢复输入
- runtime 恢复执行并获得最终 tool result

Python CLI 在当前阶段可以把这套过程包成同步表现：DM 在终端里直接回答，runtime 当场恢复，因此对使用者看起来像“调用 ask，立刻拿到结果”。

选择理由：
- 这同时满足 CLI 易用性和未来多宿主扩展性。
- 这比把底层直接定义成阻塞式工具更适合后续 HTTP。
- 这让 agent 逻辑不必知道宿主到底是同步还是异步。

备选方案：
- 底层直接定义为同步阻塞工具。未采用，因为这会把长期运行时绑死在 CLI 风格上。
- 底层只做 request/response 对象，不提供恢复语义。未采用，因为这仍然需要外层手工串联控制流。

### 决策 3：Context Agent 的“继续跑”通过恢复执行实现，而不是强依赖原地协程续跑

恢复后是否精确从某一行代码继续，不应成为长期约束。运行时可以采用“带着恢复输入重放当前 agent step / 推理轮”的方式，只要对 agent 作者表现为 ask 之后可以继续生成结果即可。

选择理由：
- 这与多数 LLM runtime 的现实更一致：所谓继续执行，常常是带着新 state / tool result 再跑一轮。
- 这避免为了一次 ask 恢复引入复杂的协程快照机制。
- 这和 LangGraph interrupt/resume 的节点重放思路兼容，但不要求业务方显式建图。

备选方案：
- 强制要求精确原地恢复。未采用，因为实现复杂且对当前项目收益不高。
- 每次 ask 后完全交给外层重建业务逻辑。未采用，因为这又退回 request emitter 模型。

### 决策 4：runtime 需要区分 pending interrupt 与恢复后的 tool result

运行时需要有明确的中间状态，区分：
- ask 已发起，但仍等待宿主回答
- ask 已恢复，并返回结构化 `AskResponse`

这类状态必须能被 planner 结果、eval 脚本和测试观察到，不能只存在于内部隐式控制流里。

选择理由：
- 没有中间状态，就无法同时支持 CLI 同步 facade 和未来异步宿主。
- 这让测试能够断言 interrupt 是否正确发生和恢复。
- 这让 eval 能观察 pending interrupt 与恢复后的最终 bundle。

备选方案：
- 不暴露 pending interrupt，只让 CLI 自动吞掉。未采用，因为这会让长期协议不清晰。

### 决策 5：eval 脚本需要从“采集 ask 回答”升级为“驱动 interrupt 恢复并展示最终结果”

在 interruptible ask 模型下，eval 脚本不应再只停在 `AskResponse` 采集。它应当：
- 观察 interrupt
- 在 CLI 中收集回答
- 驱动 runtime 恢复
- 展示恢复后的最终 `ContextBundle`

选择理由：
- 这才符合“Context Agent 问完继续生成结果”的目标。
- 这样 eval 就真正反映长期 ask 语义，而不是临时外层拼装。

备选方案：
- 让 eval 继续只展示 ask 并停住。未采用，因为这无法验证 interruptible tool 的完整行为。

## 风险 / 权衡

- [中断恢复语义引入新的 runtime 复杂度] → 通过先只覆盖 ask，并把宿主差异限制在 adapter 层来收敛范围。
- [CLI 同步 facade 掩盖底层异步真相] → 在 design、spec 和结果字段中明确 pending interrupt / resumed result 的区别。
- [Context Agent 恢复后重跑会带来重复工具调用] → 允许实现阶段通过缓存或 state 注入减少重复，但不把“原地恢复”作为必要前提。
- [现有 ask/eval 行为会发生明显变化] → 通过增量 specs 明确这是行为升级，并在测试中固定新控制流。

## 迁移计划

1. 先新增 `interruptible-agent-tools` 规范，定义可中断工具的运行时语义。
2. 修改 `agent-ask-tool` 规范，把 ask 从请求构造工具升级为 interruptible tool。
3. 修改 `agent-planner` 规范，要求 Context Agent 在 ask 恢复后继续生成结果。
4. 修改 `context-agent-eval-script` 规范，让 eval 路径观察 interrupt、恢复并展示最终 bundle。
5. 实现阶段先在 Python CLI 上验证同步 facade，再考虑其他宿主。

回滚策略：
- 若运行时 interrupt 方案短期内不稳定，可先保留 pending interrupt 结构和 CLI facade，但暂时限制为单轮 ask 恢复。
- 若恢复执行路径复杂度过高，可先采用“带着恢复输入重跑当前 agent step”的方式，而不是追求原地恢复。

## 开放问题

- interrupt 状态是否需要单独的结构化对象，例如 `ToolInterrupt` / `PendingInterrupt`，还是沿用现有 planner 结果字段扩展即可。
- 恢复输入是否仅包含 `AskResponse`，还是需要同时带上 interrupt id / run id 等标识。
- Python CLI 的同步 facade 是放在通用 runtime adapter，还是仅先放在 eval runner 中验证。
