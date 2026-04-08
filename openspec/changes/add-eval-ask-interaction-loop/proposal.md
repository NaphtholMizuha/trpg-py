## 为什么

现在 Context Agent 已经能产出结构化 `ask_requests`，但 eval 脚本还没有把它真正变成一次可执行的 DM 交互回合。开发者虽然能看到 ask 请求，却不能在同一条 eval 路径里完成选择、使用默认值或输入自定义答案，因此无法验证 ask 契约在真实 CLI 场景中的可用性。

现在需要补上这条闭环：让 eval 脚本在 Python CLI 中实际展示 ask、采集 DM 回答，并把回答整理成统一的 `AskResponse` 结果，用于后续继续调试或手动推进流程。

## 变更内容

- 修改 Context Agent eval 脚本，使其在交互式 Python CLI 下真正执行 ask 交互，而不只是打印 `ask_requests`。
- 要求 eval 脚本支持 ask 请求中的预设选项、默认值和自定义输入，并把 DM 的回答收集成统一 `AskResponse` 列表。
- 要求 eval 脚本在一次运行中同时展示：原始 ask 请求、DM 选择结果，以及回填后的结构化 ask 响应，便于手动验证和留档。
- 明确本次闭环只落在 eval / CLI 调试路径，不要求在本 change 中实现完整的 planner 多轮恢复执行。
- 补齐自动测试，覆盖默认选择、自定义输入、非交互模式以及 ask 结果展示的行为。

## 功能 (Capabilities)

### 新增功能
- 无

### 修改功能
- `agent-ask-tool`: 扩展 ask tool 的消费约束，要求 Python CLI eval 路径能够按统一 ask 契约实际采集并返回 `AskResponse`。
- `context-agent-eval-script`: 扩展 Context Agent eval 脚本，使其支持真实 ask 交互、结果展示和结构化回填。
- `planner-e2e-eval-suite`: 明确子 agent 专项 eval 可以在 CLI 内完成 ask 交互闭环，而端到端批量评测仍不承担完整子 agent 交互调试职责。

## 影响

- 受影响代码主要包括 `src/augury/agent/context_eval.py`、`src/eval/context_agent_eval.py`、CLI ask adapter 以及相关测试。
- 需要把当前“只展示 ask 请求”的 eval 行为收口成“展示并采集 ask 响应”的正式能力。
- 不引入新的交互宿主；本次仍只实现 Python CLI，且继续沿用统一 ask 契约。
- 不要求这次实现直接把 ask 回答重新注入 planner / resolution 执行链，但输出必须足够结构化，方便下一步继续接闭环执行。
