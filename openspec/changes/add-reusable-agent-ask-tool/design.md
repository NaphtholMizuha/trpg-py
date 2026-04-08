## 上下文

当前 Context Agent 在证据不足时只能以 `needs_human` / `blocked` 这类状态暴露“还需要 DM 介入”，但缺少一条稳定的结构化出口来承载具体提问。这让“哪里需要 DM 决定”虽然能被看见，却还不是一等交互对象，调用方很难把它渲染成稳定交互，更难复用于其他 agent。

你现在要的不是再加一段自由文本问题，而是一个长期可复用的 `ask` tool。它先给 Context Agent 用，但本质上属于 agent runtime 的通用交互能力：任何 agent 在遇到“已有足够候选、但仍需人来拍板”的场景时，都应该可以发出同一种结构化澄清请求。

这个设计还受到当前 runtime 约束：agent 侧并没有真正的同步人机回合，因此 `ask` 不能被设计成一个会在工具内部阻塞等待 DM 回复的调用。它更适合被设计成“生成一个可交付给上层 UI / 调用方的澄清请求对象”，然后由外层系统决定如何展示和回填。

还有一个新的实现边界需要先钉住：短期内只需要支持 Python CLI 作为 ask 的实际交互宿主，但 ask 协议本身不能因此退化成 CLI 私有格式。也就是说，实现可以先只有 CLI adapter，数据契约仍然必须保持 transport-agnostic，给后续 HTTP 或其他宿主留下稳定边界。

## 目标 / 非目标

**目标：**

- 为 agent runtime 增加一个可复用的 `ask` tool，而不是 Context Agent 私有 helper。
- 要求 ask 请求同时支持候选选项、默认值和自定义输入入口。
- 让 Context Agent 在遇到可提问的歧义或缺失时优先产出结构化 `ask_requests`，并让它成为面向上层的主交互出口。
- 让 planner 对外结果能暴露 ask 请求，便于上层系统或手动 eval 观察。
- 为主 agent / Context Agent 增加长期 prompt 约束，明确何时 ask、如何组织选项和默认值。
- 先为 Python CLI 提供 ask 的实际展示与回填实现，同时保持 ask 协议对未来 HTTP 接口可复用。

**非目标：**

- 本次设计不实现完整的人机多轮会话状态机。
- 本次设计不要求 ask tool 立即接通真实前端控件或持久化答复存储。
- 本次设计不定义所有 agent 都必须默认加载 ask tool；这里只要求它可复用，并先装配给 Context Agent。
- 本次设计不扩展成复杂表单系统，例如多问题分页、条件分支问卷或富媒体输入。
- 本次设计不要求立即实现 HTTP、WebSocket 或前端 UI 的 ask 适配层。

## 决策

### 决策 1：将 ask 设计成通用 agent tool，而不是 Context Agent 私有逻辑

`ask` 应属于通用工具层。Context Agent 只是第一个默认装配它的消费者，后续其他 agent 也可以挂载同一工具。

选择理由：

- 这符合“以后可能还会装载到其他 agent 上面”的目标。
- 这避免每个 agent 各自发明一套人类澄清结构。
- 这让 UI、测试和日志层只需支持一种 ask 协议。

备选方案：

- 把 ask 逻辑内嵌在 Context Agent。未采用，因为这样后续复用时会复制协议。
- 把 ask 设计成主 agent 专属能力。未采用，因为实际首先遇到歧义的是子 agent，而且其他 agent 也会需要同类交互。

### 决策 2：ask tool 生成结构化 AskRequest，而不是在工具内部等待回答

ask tool 的职责是生成结构化澄清请求对象，例如：

- `question_id`
- `prompt`
- `options`
- `default_option_id`
- `allow_custom_input`
- `custom_input_label`
- `custom_input_placeholder`
- `reason`

agent 调用 ask tool 后，应将该请求对象带回其 bundle 或 planner 结果，由外层调用方决定如何展示并收集回答。

选择理由：

- 当前 runtime 没有同步阻塞式人机回合。
- 结构化 AskRequest 更容易进入测试、日志、eval 和 UI。
- 这让 ask tool 对任何 agent 都是一致的“构造请求”能力。

备选方案：

- 让 ask tool 在调用时直接等待 DM 输入。未采用，因为这会把 runtime 与特定交互宿主强耦合。
- 不新增工具，只把 ask 信息塞进普通缺口文本。未采用，因为这无法稳定表达选项、默认值和自定义输入。

### 决策 3：统一 ask 契约与 CLI 实现方式分离

本次实现只需要提供 Python CLI 的 ask 适配层，但 ask 的核心协议仍然应保持统一。也就是说：

- agent / runtime 只依赖 `AskRequest` / `AskResponse`
- Python CLI 负责把 AskRequest 渲染成终端可交互的问题，并把用户选择或自定义输入回填成 AskResponse
- 未来如果接入 HTTP，只新增新的宿主适配层，而不改变 agent 侧 ask 协议

选择理由：

- 这符合“目前只需要实现 python cli，但是统一契约还是要的”的边界。
- 这样可以先把真实可用路径做出来，同时不给后续 HTTP 接入埋协议债。
- 测试也能分层：协议测试与 CLI adapter 测试分开。

备选方案：

- 直接把 ask 设计成 CLI 专属格式。未采用，因为后续接 HTTP 时会迫使 agent/runtime 一起返工。
- 一开始同时实现 CLI 和 HTTP。未采用，因为这超出当前实现范围。
### 决策 4：AskRequest 必须同时支持 options、default 和 custom input

AskRequest 至少应支持：

- 预设选项列表 `options`
- 一个推荐或默认选项 `default_option_id`
- 允许自定义输入 `allow_custom_input`
- 自定义输入的标签和占位提示

选择理由：

- 只有选项没有默认值时，agent 很难表达它认为最可能的安全路径。
- 只有默认值没有自定义输入时，会把 DM 锁死在有限候选中。
- 这三者组合能覆盖大多数“歧义但可澄清”的场景，例如目标选择、爆点位置、规则版本偏好、环境解释等。

备选方案：

- 只支持纯文本问题。未采用，因为无法表达默认建议与有限候选。
- 只支持单选题。未采用，因为 DM 可能需要输入一个未出现在候选中的自定义值。

### 决策 5：Context Agent 在“可明确提问”时优先生成 ask_requests，而不是继续把面向 DM 的缺口做成普通文本

当 Context Agent 已经能够把缺口收敛成明确问题时，应优先构造 ask 请求。例如：

- 目标片段 `goblin` 匹配多个实体时，列出 `goblin_1` / `goblin_2` 作为选项。
- 火球术缺少爆点时，给出默认处理选项和自定义位置输入入口。

如果某个问题已经能收敛成明确提问，它就应进入 `ask_requests`。无法收敛成明确提问的内部问题，可继续留在内部备注或错误语义里，但不再作为面向 DM 的主返回承载。

选择理由：

- ask 的价值在于把“缺口”升级成“可执行的人类确认动作”。
- 这能减少调用方再去二次解释松散缺口文本。

备选方案：

- 所有缺口都强制 ask。未采用，因为有些缺口只是系统暂时无法理解，不适合伪装成明确问题。
- 完全不保留任何内部失败说明。未采用，因为 ask 之外仍然会有搜索失败、动作类型不认识等非交互性问题。

### 决策 6：planner 结果需要显式承载 ask_requests，并让它成为面向 DM 的主要缺口出口

为了让外层真正消费 ask tool，planner / Context Agent 相关结构化结果需要暴露 `ask_requests` 或等价字段。面向 DM 的澄清需求应优先进入这个字段，而不是继续停留在 `notes`、`missing_info` 或其他松散文本里。

选择理由：

- ask 是一等交互对象，不应该被降级成附注。
- 这让手动 eval 和自动测试可以直接断言 ask 是否被正确生成。

备选方案：

- 只在 ContextBundle 里暴露 ask，不在 PlannerResult 中透出。未采用，因为主 agent 之外的调用方最终消费的是 planner 结果。

## 风险 / 权衡

- [ask 用得过多，agent 遇到小缺口就把问题甩给 DM] → 通过 prompt 约束要求只有“可明确提问且人类确认能直接解锁后续流程”的情况才允许 ask。
- [选项和默认值设计得太武断，误导 DM] → 要求 ask 请求同时暴露推荐理由，并保留自定义输入入口。
- [不同 agent 未来会需要不同类型的 ask] → 当前先统一最小协议：单个问题、有限 options、一个默认值、可选自定义输入；后续再增量扩展。
- [先做 CLI 会让 ask 协议被 CLI 细节污染] → 把宿主相关行为收敛到 CLI adapter，agent/runtime 只依赖统一 AskRequest / AskResponse。
- [现有结果结构不承载 ask，导致实现分散] → 在 runtime 与 planner 结果里增加一等字段，而不是把 ask 信息塞回 notes 或普通缺口文本。

## 迁移计划

1. 先新增 `agent-ask-tool` 规范，定义 AskRequest 的最小结构与交互边界。
2. 修改 runtime 与 planner 相关规范，要求 Context Agent 默认可装配 ask，且 planner 结果可显式暴露 ask 请求。
3. 明确 ask 的统一协议与 Python CLI adapter 的边界，保证短期只实现 CLI 也不会污染长期接口。
4. 修改主 agent / Context Agent 的 prompt 规范，明确何时 ask，如何给选项、默认值和自定义输入。
5. 实现阶段先补工具、模型、CLI 适配、测试和 eval 展示。

回滚策略：

- 若实现阶段发现 planner 结果暂时难以完整承载 ask 请求，可先在 ContextBundle 中落地 ask_requests，并保留向 PlannerResult 透传的兼容层。
- 若默认值策略一时难以统一，可先要求 ask 请求必须支持 `default_option_id` 字段，即使部分场景暂时留空，但不回退整个 ask 协议。

## 开放问题

- AskRequest 的 `options` 是否需要额外区分“推荐项”和“普通项”，还是只保留一个 `default_option_id` 即可。
- 自定义输入回填后，后续 agent 如何接收与消费该答案，是通过 planner 重新调用，还是通过独立回复注入。
- 是否需要在 ask 请求里显式加入 `agent_id` / `source_agent` 字段，方便多 agent 并存时追踪来源。
- Python CLI 的 ask adapter 是走同步阻塞输入，还是先生成请求对象再由 runner 统一处理。
