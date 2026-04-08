## 为什么

当前项目已经把长期运行时真相切换到主 agent 委派架构，但评测入口仍然主要围绕自动测试和端到端 fixture 组织，缺少一个专门面向子 agent 的可观察评测脚本。对于 Context Agent 这种负责收集规则和世界状态证据的子 agent，仅看单元测试断言不够直观，也不利于快速观察主 agent 实际会委派给它的输入和它实时返回的 bundle。

现在需要补一条更清晰的开发者路径：在 `src/` 下新增与 `augury/`、`tests/` 平级的 `eval/` 目录，并提供一个完整的 Context Agent eval 脚本，用于直接复现“主 agent -> Context Agent”的默认输入输出契约，展示规则证据、状态证据、来源定位、未决缺口和摘要信息。

## 变更内容

- 在 `src/` 下新增与 `augury/`、`tests/` 平级的 `eval/` 目录，作为长期保留的手动评测脚本入口。
- 新增一个专门测试 Context Agent 的 eval 脚本，输入必须与主 agent 委派给 Context Agent 的默认 payload 结构一致，而不是临时设计另一套专用参数。
- 该脚本必须输出 Context Agent 实时返回的结构化 bundle，并以人类可读方式展示至少 instruction、normalized instruction、action、resolved entities、rule evidence、state evidence、citations、unresolved gaps、notes 和 status。
- 脚本必须支持加载默认 world state fixture，并允许开发者覆盖 instruction、state 文件或输出格式，以便复现实战委派场景。
- **BREAKING** 调整项目对 `src/` 顶层验证目录的长期约束：正式可保留的验证目录不再只有 `src/tests/`，还包括 `src/eval/` 这一类人工运行但结构化的评测入口。

## 功能 (Capabilities)

### 新增功能
- `context-agent-eval-script`: 定义 Context Agent 的手动评测脚本、输入契约、输出 bundle 展示要求，以及默认运行方式。

### 修改功能
- `src-project-layout`: 调整 `src/` 顶层布局约束，允许新增与 `augury/`、`tests/` 平级的 `eval/` 目录来承载长期保留的结构化评测脚本。
- `agent-planner`: 补充主 agent 到 Context Agent 的默认委派输入应可被独立评测脚本直接复现和观察的要求。
- `planner-e2e-eval-suite`: 区分端到端评测与子 agent 评测职责，明确 Context Agent 的专门 eval 脚本不应继续挤进端到端 fixture 入口。

## 影响

- 受影响代码主要包括 `src/augury/agent/`、新的 `src/eval/`、默认 world state fixture 装载逻辑，以及部分 `src/tests/` 中对评测入口的说明或辅助代码。
- 项目目录约束会发生变化，需要把 `src/eval/` 纳入长期布局真相。
- 开发者将获得一个新的手动评测入口，用于独立观察 Context Agent 的 bundle，而不是只能通过测试断言或完整 planner 流程间接观察。
