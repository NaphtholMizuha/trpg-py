## 上下文

当前项目已经把 planner 的长期运行时真相切到主 agent 委派架构，`Context Agent` 负责消费主 agent 传入的 instruction/state/context payload，返回 `ContextBundle`。与此同时，验证真相目前主要有两类：

- `src/tests/` 中的自动测试，适合断言稳定行为。
- `examples/evals/` 中的固定 fixture，适合端到端回归。

缺口在于，项目还没有一个专门面向“单个子 agent 可观察调试”的长期入口。对于 Context Agent，开发者现在很难快速回答下面这些问题：

- 主 agent 实际会如何构造委派给它的 payload？
- Context Agent 当前返回的 bundle 里到底有哪些字段？
- 哪些 rule/state evidence 是实时拿到的，哪些缺口会直接导致 `needs_human` 或 `blocked`？

这次设计要补的不是新的 smoke 目录，而是一条更明确的评测路径：在 `src/` 下新增 `eval/` 目录，专门放长期保留、结构化、可人工运行的 eval 脚本；其中第一条脚本就是 Context Agent eval runner。

## 目标 / 非目标

**目标：**

- 在 `src/` 下新增与 `augury/`、`tests/` 平级的 `eval/` 目录。
- 为 Context Agent 提供一个完整的手动 eval 脚本，而不是把观察面继续塞回 tests 或已删除的 smoke。
- 要求该脚本直接复用主 agent 委派给 Context Agent 的默认 payload 结构。
- 要求该脚本实时打印结构化 `ContextBundle`，并突出关键观察字段。
- 让该脚本默认可加载版本化 world state fixture，同时允许覆盖 instruction、state 文件与输出格式。

**非目标：**

- 本次设计不新增新的子 agent 类型。
- 本次设计不重写 Context Agent 的内部推理策略，只关注它的评测入口与观察面。
- 本次设计不把 `src/eval/` 扩展成新的杂项脚本目录；这里只承载长期保留、结构化的 eval runner。
- 本次设计不替代 `src/tests/` 的自动测试职责，也不替代端到端 fixture 套件。

## 决策

### 决策 1：在 `src/` 下新增 `eval/`，而不是恢复 `smoke/`

`src/eval/` 将成为与 `src/tests/` 并列的长期目录，用于放置人工运行但结构化的评测脚本。它和旧 `smoke/` 的差别在于：

- `eval/` 不是“想到什么就丢什么”的临时脚本区。
- `eval/` 中的入口必须围绕稳定输入契约、稳定输出结构和固定夹具组织。
- `eval/` 的观察面应服务于 agent/runtime 调试，而不是再次演化成架构真相本身。

备选方案：

- 把脚本放进 `src/tests/`。未采用，因为手动运行观察面和自动测试职责不同。
- 恢复 `src/smoke/`。未采用，因为这会把项目重新带回刚刚清理掉的长期双轨真相。

### 决策 2：Context Agent eval 脚本的输入必须复用主 agent 委派 payload

脚本将直接构造与主 agent `delegate(context_agent, payload)` 一致的 payload。最小字段至少包括：

- `instruction`
- `state`
- `context`

如果未来主 agent 给 Context Agent 增加新的默认字段，eval 脚本也应同步更新，而不是维护一套“只用于脚本”的简化输入格式。

备选方案：

- 让脚本只接受一条 instruction，然后内部拼凑最小输入。未采用，因为这会让脚本脱离真实委派接口。
- 让脚本直接调用主 agent，而不是直接调 Context Agent。未采用，因为这会把观察面重新抬回完整 workflow，失去子 agent 定位价值。

### 决策 3：脚本输出必须展示实时 bundle 的关键字段，而不是只打印原始 JSON

脚本应同时支持两层输出：

- 默认人类可读视图：突出 `status`、`action`、`resolved_entities`、`rule_evidence`、`state_evidence`、`citations`、`unresolved_gaps`、`notes`。
- 可选 JSON 视图：输出完整 bundle 以便复制、比对或落日志。

默认视图必须让开发者一眼看出：

- 这次 instruction 被识别成什么 action。
- Context Agent 认为哪些实体已解析。
- 命中了哪些规则和状态证据。
- 当前还缺哪些关键信息。

备选方案：

- 仅打印 `bundle.model_dump_json()`。未采用，因为不够可读，也不利于快速观察。
- 只输出精简摘要。未采用，因为会丢掉高信息密度 bundle 的核心价值。

### 决策 4：默认 state 来源继续使用版本化 fixture，而不是内联样例

Context Agent eval 脚本应默认使用仓库中的版本化 world state fixture，并支持 `--state-file` 覆盖。这样脚本输出才会和真实 planner 评测、自动测试共享同一批状态语义。

备选方案：

- 在脚本里内联一个极简 state。未采用，因为它和实际运行态容易偏离。
- 强制调用方每次都手传 state 文件。未采用，因为默认可运行性会变差。

## 风险 / 权衡

- `src/eval/` 可能再次膨胀成新的“脚本堆场” → 通过规范把它限定为长期保留、结构化、契约清晰的 eval runner 目录。
- Context Agent 输入契约未来变化后，脚本可能滞后 → 要求脚本复用主 agent 默认委派 payload，并通过测试覆盖脚本的输入结构。
- 默认人类可读输出过长 → 通过分段展示关键字段，并保留 `--json` 作为完整输出通道。
- 如果 search 使用真实后端，脚本结果可能受环境影响 → 默认允许使用与项目一致的真实链路，同时保留 fixture/state 覆盖和必要的降级说明。

## 迁移计划

1. 先在 `src/` 下引入 `eval/` 目录，并声明其长期职责。
2. 新增 Context Agent eval 脚本，先支持默认 fixture、instruction 覆盖和 bundle 展示。
3. 为脚本补自动测试，验证输入结构和关键输出字段。
4. 更新 README 或开发者文档，把该脚本加入推荐调试路径。

回滚策略：

- 若 `src/eval/` 的职责定义被证明过宽，可以保留脚本本身，但把目录职责重新收紧到单一 Context Agent runner。
- 若手动评测入口造成维护负担，可以只保留最小 runner，并继续把更多断言放回 `src/tests/`。

## 开放问题

- Context Agent eval 脚本是否还需要把 payload 一并打印出来，作为“主 agent 实际委派输入”的观察面。
- 是否需要为该脚本补一个 `--output-file`，方便把 bundle 快照存档。
- 后续是否要为 Resolution Agent 提供同类 eval runner，保持 `src/eval/` 目录对称。
