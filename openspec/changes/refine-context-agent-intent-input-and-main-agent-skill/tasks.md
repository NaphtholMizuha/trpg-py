## 1. 委派输入契约

- [x] 1.1 将主 agent 到 Context Agent 的默认 payload builder 从 `instruction/state/context` 调整为 `intent/goal/requests`
- [x] 1.2 明确 `intent`、`goal`、`requests` 的生成规则，并确保 `requests` 是可操作的自然语言事实获取请求
- [x] 1.3 调整 Context Agent 对新输入契约的消费逻辑，移除对 `state/context` 作为长期输入字段的依赖

## 2. 主 Agent Skill / Prompt

- [x] 2.1 为主 agent 增加或调整默认 skill / prompt 约束，明确其在调用 Context Agent 前必须先整理 `intent`、`goal`、`requests`
- [x] 2.2 为典型任务形态补主 agent 构造 `requests` 的示例，避免回退成问句列表、字段名列表或直接转发原始 instruction

## 3. Context Agent Eval 与测试

- [x] 3.1 调整 Context Agent eval helper 与脚本，使其默认展示新的 `intent.goal.requests` 输入
- [x] 3.2 补强自动测试，覆盖新 payload 的构造、展示和 `requests` 的自然语言语义
- [x] 3.3 更新或新增测试，验证新的委派输入仍能驱动 Context Agent 返回稳定的 `ContextBundle`

## 4. 文档与收口

- [x] 4.1 更新相关文档或说明，解释为什么 Context Agent 的输入改为事实获取任务而不是原始 instruction 转发
- [x] 4.2 运行相关自动测试与 eval 自检，确认新契约、主 agent skill 约束和 Context Agent 观察入口一致
