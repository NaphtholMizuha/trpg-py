## 上下文

当前 planner 已经拆成 `task_node -> dsl_node` 两阶段，但 `task_node` 这一层还缺一个稳定的手动验证入口。自动测试适合约束接口和流程，却不适合观察一条真实指令在当前 prompt、当前 world state、当前工具边界下会被翻译成什么样的 `TaskDraft`。

仓库里已经有一组 `src/smoke/test_*.py` 脚本，用来人工验证 tool 与 workflow 的关键能力。新的 `task_node` 也需要一个同风格入口，让开发者在调整 prompt、模型或状态文件后，能快速看到：
- `task` 是怎么写的
- `reads / judgments / writes` 是否合理
- `missing_info` 是否过多或过少
- `TaskDraft` 是否还能成功结构化返回

## 目标 / 非目标

**目标：**
- 新增一个专门验证 `task_node -> TaskDraft` 的 smoke 脚本。
- 保持脚本风格与现有 `src/smoke/test_grep.py`、`src/smoke/test_reads.py` 一致，可直接命令行运行。
- 允许脚本使用默认 world state，也允许显式指定 state 文件和自定义 instruction。
- 让脚本既支持人类可读输出，也支持 JSON 输出，方便人工观察和后续最小自动测试。

**非目标：**
- 不在这次变更里新增 `dsl_node` 的 smoke 脚本。
- 不把 smoke 脚本变成新的自动测试主入口。
- 不在这次变更里重做 `task_node` 的 prompt 或工具协议。
- 不要求 smoke 脚本覆盖所有任务类型，只要能稳定观察 `TaskDraft` 产出即可。

## 决策

### 决策 1：新增独立脚本 `src/smoke/test_task.py`

脚本必须单独存在于 `src/smoke/test_task.py`，而不是把 `task_node` 验证混进现有 workflow 或 tool smoke 里。

这样做的原因是：
- `task_node` 的关注点是“把指令翻译成任务稿”，与 `dsl_node` 和单个 tool 的 smoke 关注点不同
- 独立脚本更方便后续单独迭代默认 instruction 与展示格式
- 开发者调试第一阶段时不必经过完整 workflow

替代方案：
- 把能力塞进 `test_planner_workflow.py`：适合自动测试，不适合作为人工观察入口
- 直接复用未来的完整 planner smoke：观察粒度太粗

### 决策 2：脚本直接调用真实 `TaskNode`

脚本必须实例化真实 `TaskNode`，并为它注入真实 `grep` / `read` / 可选 `search` 工具与项目配置，而不是构造假 agent 或只打印固定样例。

这样做的原因是：
- smoke 的意义就在于验证真实 prompt、真实配置、真实工具边界
- 这样才能捕捉到 prompt 模板、配置文件、结构化输出 schema 之间的漂移

替代方案：
- 用 fake agent：更稳定，但失去 smoke 价值
- 直接调用底层模型而不是 `TaskNode`：会绕开节点真实装配路径

### 决策 3：输出契约围绕 `TaskDraft` 关键字段

脚本的人类可读输出必须至少展示：
- `instruction`
- `task`
- `reads`
- `judgments`
- `writes`
- `missing_info`
- `assumptions`

JSON 模式必须输出完整 `TaskDraft.model_dump()` 结果，禁止只输出截断摘要。

这样做的原因是：
- 这些字段正是第一阶段对第二阶段的契约
- 开发者调 prompt 时，最关心的是这些字段是否合理，而不是 agent 原始消息细节

替代方案：
- 只输出一段 summary：不够稳定，也不利于对比
- 打印全部内部日志：噪音过大

### 决策 4：保留最小自动验证，但不把 smoke 语义自动化过度

应当补充最小自动测试，至少覆盖：
- 脚本可以成功运行
- `--json` 输出可解析
- 输出中包含 `TaskDraft` 的关键字段

但测试不应强绑定某个真实模型返回的具体自然语言内容。

这样做的原因是：
- smoke 脚本仍需要基本防回归保护
- 真实语言内容会随 prompt 和模型微调，不适合写成脆弱断言

替代方案：
- 完全不加测试：容易被重构悄悄打断
- 对自然语言全文做快照断言：维护成本太高

## 风险 / 权衡

- [真实 `TaskNode` smoke 依赖模型与配置] → 通过提供 `--json` 和最小入口测试，把自动验证收敛在脚本协议层，而把语言质量观察留给人工运行。
- [脚本输出可能随着 prompt 演进而变化] → 只把字段存在性和基本格式作为自动测试契约。
- [不同 state 文件会导致 TaskDraft 差异较大] → 提供默认 world state，并允许显式传参覆盖。

## Migration Plan

1. 新增 `src/smoke/test_task.py`，按现有 smoke 脚本风格提供 CLI。
2. 在脚本中装配真实 `TaskNode` 和默认状态加载逻辑。
3. 增加最小自动测试，验证脚本入口和 JSON 输出。
4. 让该 smoke 脚本成为调试 `task_node` 的推荐手动入口。

## Open Questions

- 默认 instruction 应该选一个简单稳定的攻击/施法示例，还是改为命令行必填？
- 是否需要在第一版里暴露 `--config` 参数，以便显式切换 prompt 与模型配置？
