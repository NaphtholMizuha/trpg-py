## 上下文

当前仓库已经能分别观察 `task_node`、`dsl_node` 和单条 smoke 的行为，但还没有一套固定的端到端评测矩阵来回答三个问题：

1. 同一套世界状态下，10 条代表性指令经过 planner 和 engine 后是否仍然稳定。
2. 当 prompt、workflow 或 engine 改动时，退化发生在 `TaskDraft`、`TaskDocument`、lint、还是 execution。
3. 哪些案例本来就应该 `needs_human`，哪些案例应该完整执行成功。

现有 `src/smoke/test_task.py` 和 `src/smoke/test_dsl.py` 已经提供了节点级观察入口，也已有固定骰子和状态变更摘要工具；因此这次更适合新增一层“批量端到端评测 harness”，而不是重新发明独立的 planner/engine 调用方式。

利益相关者是维护 prompt、workflow、lint 和 engine 的开发者。主要约束是：
- 必须使用真实 planner workflow，而不是 fake agent。
- 必须使用固定 world state 和固定骰子，保证重复运行结果可比。
- 评估不能强依赖整段自然语言完全一致，必须更多依赖结构化信号。

## 目标 / 非目标

**目标：**
- 提供一套专门为端到端评测设计的固定 world state fixture。
- 提供 10 条覆盖关键任务形态的黄金输入，覆盖攻击、治疗、范围法术、缺信息和状态投影。
- 提供一个批量运行入口，逐案例执行 instruction -> planner workflow -> engine。
- 为每个案例记录中间产物和最终结果，包括 `TaskDraft`、`TaskDocument`、`lint_result`、`execution_result` 和状态变化。
- 提供稳定的自动评分摘要，能快速看出哪些案例通过、失败、退化或命中了预期的 `needs_human`。

**非目标：**
- 不在这次变更里引入新的训练数据或新的模型提示词策略。
- 不要求每条案例都用全文字符串精确匹配 `task` 或 `judgments`。
- 不把评测 harness 扩展成通用 benchmark 平台、数据库服务或持续集成 SaaS。
- 不在这次变更里重构 planner workflow 的公开接口。

## 决策

### 决策 1：使用单独的评测 fixture bundle，而不是复用默认 smoke world state
- 选择原因：默认 `config/world_state.toml` 更像开发中的通用示例，不适合长期承担“黄金评测数据”职责。评测需要一个显式版本化的 fixture bundle，包含世界状态和案例清单，便于后续审阅与扩展。
- 方案：
  - 在仓库内新增一组评测 fixture，包含：
    - 一个固定 world state TOML
    - 一个 10 案例 manifest
    - 每个案例的结构化期望
  - 推荐路径放在 `examples/evals/planner_e2e/`，因为它们属于静态示例数据，而不是运行配置。
- 备选方案：
  - 直接复用 `config/world_state.toml`
  - 每个案例各自维护独立 world state
- 不选原因：
  - 复用默认 smoke state 容易被日常调试改动污染。
  - 每案例单独 state 虽然隔离强，但会削弱“同一世界下跨案例比较”的价值，并增加维护成本。

### 决策 2：新增一个端到端批量评测入口，而不是把能力拆散到多个脚本
- 选择原因：用户要的是“从指令到 engine 的全流程”评测，而不是再次分别跑 task smoke 和 dsl smoke。一个批量入口更容易形成统一日志和汇总。
- 方案：
  - 新增一个 `src/smoke/` 下的批量评测脚本，例如 `src/smoke/test_planner_engine_eval.py`
  - 该脚本逐条读取案例：
    - 加载初始 world state
    - 调用真实 `PlannerWorkflow`
    - 若结果为 `ready` 且 `lint` 有效，则执行 engine
    - 生成单案例日志和总汇总
- 备选方案：
  - 扩展现有单条 smoke 脚本并叠加大量参数
  - 把能力做成新的 `src/evals/` 目录
- 不选原因：
  - 直接把现有单条 smoke 改成“大而全”会让单案例调试入口变笨重。
  - 新建 `src/evals/` 会引入新的目录语义，超出这次提案必要范围。

### 决策 3：评估以“结构化 expectation” 为主，而不是全文精确匹配
- 选择原因：LLM 的自然语言表述会波动，但好的回归评估应关注结构是否正确、路径是否合理、execution 是否达成预期。
- 方案：
  - 每个案例在 manifest 中声明结构化期望，例如：
    - `expected_workflow_status`
    - `expected_missing_info_contains`
    - `expected_read_paths`
    - `expected_write_paths`
    - `expected_step_signatures`，如 `select.area` / `check.save` / `damage.apply`
    - `expected_lint_status`
    - `expected_execution_status`
    - `expected_changed_paths`
    - `expected_unchanged_paths`
  - evaluator 根据这些字段生成 pass/fail 和 failure reasons。
- 备选方案：
  - 用完整 `TaskDraft` / `TaskDocument` 快照做字面比较
  - 只看 execution 最终是否成功
- 不选原因：
  - 字面比较对 prompt 漂移过于脆弱。
  - 只看 execution 会掩盖 `TaskDraft` 和 lowering 质量问题。

### 决策 4：每个案例都记录完整中间产物，并将评分结果写回同一日志
- 选择原因：一旦案例失败，开发者必须能立刻看到它失败在什么阶段，而不是重新手动复现。
- 方案：
  - 每个案例生成一个 JSON 日志，至少包含：
    - `case_id`
    - `instruction`
    - `initial_state_file`
    - `workflow_result.status`
    - `draft`
    - `missing_info`
    - `task_document`
    - `lint_result`
    - `execution_result`
    - `state_changes`
    - `evaluation`
  - 汇总文件包含总分、通过率、各类失败统计和每条案例的快速摘要。
- 备选方案：
  - 只输出控制台摘要
  - 中间产物分散到多个目录
- 不选原因：
  - 只看控制台不利于复盘和 diff。
  - 分散日志会让“单案例全链路”难以浏览。

### 决策 5：10 条案例使用同一套战斗场景，并显式混合“应成功”与“应暴露缺口”的输入
- 选择原因：评测不仅要验证成功链路，还要验证系统在信息不足时是否诚实停下。
- 方案：
  - 设计一套专门的战斗场景，包含两名玩家角色和数个敌人、位置、资源、法术、AC、HP、豁免等信息。
  - 10 条案例建议为：
    1. `Aldera用长剑攻击goblin_1`
    2. `Goblin_2用弯刀攻击Malik`
    3. `Goblin_1用短弓攻击Aldera`
    4. `Aldera用火焰箭攻击orc_1`
    5. `Malik对自己施放治疗伤口`
    6. `Malik对Aldera施放治疗伤口`
    7. `Malik用闪电束攻击orc_1`
    8. `Aldera用火球术攻击goblin_1所在位置`
    9. `Aldera用火球术攻击goblin`
    10. `记录Aldera当前AC供下一轮使用`
  - 其中第 9 条默认期望为 `needs_human`，用于验证缺口暴露。
- 备选方案：
  - 让 10 条案例全部追求 execution success
  - 使用完全不相关的 10 套 world state
- 不选原因：
  - 全部成功样例会掩盖系统对不确定性的处理质量。
  - 多 world state 会让回归分析更分散。

## 风险 / 权衡

- [风险] 固定 10 条案例可能过拟合当前 prompt 和当前世界状态。
  - 缓解措施：使用结构化 expectation，而不是要求逐字复制；同时在 manifest 中保留案例标签，后续允许追加第二批案例。

- [风险] 某些单案例可能因为模型输出风格变化而在 `TaskDraft.task` 或 `judgments` 上出现假阳性失败。
  - 缓解措施：评分优先看路径、step signature、lint 和 execution，少量文本字段只做包含式检查。

- [风险] 端到端案例直接走真实模型，运行时间和成本高于现有单元测试。
  - 缓解措施：把该入口定义为手动 smoke / eval harness；自动测试只覆盖 manifest 解析、日志聚合和 evaluator 逻辑。

- [风险] 共享 world state 会让前一案例的状态污染后一案例。
  - 缓解措施：每个案例都从同一初始 fixture 深拷贝出独立 state，再执行 planner 和 engine。

- [风险] 评测摘要太粗，定位仍然困难。
  - 缓解措施：单案例日志中必须把 workflow、draft、DSL、lint、execution、state_changes 和 evaluation 写在同一文件里。

## 迁移计划

1. 新增评测 fixture bundle 和案例 manifest。
2. 新增批量评测脚本及其辅助评分模块。
3. 为日志格式、case schema 和 summary 聚合添加自动测试。
4. 用默认 10 案例完成一次人工 smoke，确认输出目录、日志结构和汇总可读。
5. 后续若需要扩案例，只在 manifest 中追加，不破坏已有 10 条基线。

本次变更是增量能力，不需要线上迁移或兼容性回滚。若实现效果不佳，可以删除新脚本和 fixture，而不影响现有 task/dsl smoke 入口。

## 开放问题

- 案例 manifest 使用 TOML 还是 JSON 更方便维护与 diff。
- 评测总分是否只统计 pass/fail，还是引入分层得分，例如 planning、lowering、execution 三段分数。
- `记录Aldera当前AC供下一轮使用` 这类状态投影案例是否应要求 engine 真正执行，还是只要求 planner + DSL 结果可解释。
