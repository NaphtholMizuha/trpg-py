## 上下文

当前 `dsl_node` 的主要覆盖在 [`src/tests/test_planner_workflow.py`](/home/naifen/code/trpg-py/src/tests/test_planner_workflow.py) 一类自动测试里。这些测试通过 fake `agent_factory` 直接返回固定 `TaskDocument`，适合验证：
- `DslNode` 是否把 prompt、tool、schema 正确装配进 agent
- workflow 是否会在 `task_node` 之后调用 `dsl_node`
- lint 结果是否被带回最终结果

但它们不适合回答另一个开发时更常见的问题：“当前 prompt 面对一份真实 `TaskDraft` 时，会翻译出什么 DSL？” 现有 `task_node` smoke 脚本已经为第一阶段提供了这种观察入口，而第二阶段还缺这一层。

这次变更的约束也比较清楚：
- smoke 入口应该放在 `src/smoke/`，保持与现有手动脚本一致
- 默认输入必须来自你正在使用的 `output/test_task_draft.json`
- 默认路径要走真实 `DslNode` 和真实 `lint_tool`，不能退化为 fake 响应
- 自动测试只应约束脚本协议和结构，不应快照真实模型文案

## 目标 / 非目标

**目标：**
- 新增一个专门验证 `TaskDraft -> TaskDocument` 翻译结果的 `dsl_node` smoke 脚本。
- 默认读取 `output/test_task_draft.json`，减少开发者准备输入的成本。
- 让脚本输出同时覆盖 `task_document` 与 `lint_result`，方便判断 DSL 是否既生成成功也通过校验。
- 为脚本增加最小自动测试，保证 CLI、JSON 输出和默认输入样例不会悄悄失效。

**非目标：**
- 不在这次变更里重做 `dsl_node` prompt 内容。
- 不把 smoke 脚本升级为完整 planner 端到端入口。
- 不要求自动测试验证真实模型生成的自然语言或 DSL 细节。
- 不把 `output/test_task_draft.json` 变成唯一允许的 `TaskDraft` 样例；它只是默认值。

## 决策

### 决策 1：新增独立脚本 `src/smoke/test_dsl.py`

`dsl_node` smoke 必须像 `task_node` smoke 一样拥有独立入口，而不是塞进 `test_task.py` 或完整 workflow smoke。

选择原因：
- `task_node` 和 `dsl_node` 的观察重点不同，混在一个脚本里会让输出粒度变粗
- 开发者经常需要在已有 `TaskDraft` 基础上单独调第二阶段 prompt
- 独立脚本更便于以后加入 `--draft-file`、`--json`、默认样例等参数

替代方案：
- 复用 `src/smoke/test_task.py` 并在末尾追加 `dsl_node` 调用
- 直接建议开发者写临时 Python 片段调用 `DslNode`

未选择原因：
- 前者会把“第一阶段观察”与“第二阶段观察”耦合起来
- 后者缺少稳定入口，也不符合现有 smoke 目录心智模型

### 决策 2：默认输入使用 `output/test_task_draft.json`

脚本应默认读取仓库内已有的 `output/test_task_draft.json`，并允许后续通过参数覆盖。

选择原因：
- 这是当前你已经在手动观察的样例，能够直接承接现有工作流
- 该样例是一个火球术 AoE 任务，足够复杂，能暴露 `dsl_node` 对范围、豁免、伤害和法术位消耗的翻译质量
- 使用文件而不是脚本内嵌对象，能让开发者直接编辑输入并复跑 smoke

替代方案：
- 把 `TaskDraft` fixture 硬编码在脚本里
- 让 `--draft-file` 必填

未选择原因：
- 硬编码样例会降低可编辑性
- 必填参数会增加日常调试成本

### 决策 3：脚本直接装配真实 `DslNode` 与真实 `lint_tool`

默认 smoke 路径必须实例化真实 `DslNode`，并让 `DslNode.run()` 自己完成 agent 调用与 lint。

选择原因：
- smoke 的价值就在于观察真实 prompt、真实配置、真实 schema、真实 lint 之间的联动
- 这能及时暴露 prompt 漂移、structured output 漂移或 lint 规则变化

替代方案：
- patch `DslNode.run` 返回固定 `TaskDocument`
- 只单独调用 prompt 渲染函数，不跑真实 node

未选择原因：
- 前者会失去 smoke 价值
- 后者只能看到输入提示词，无法看到最终 DSL 与 lint 结果

### 决策 4：输出契约围绕 `task_document` 与 `lint_result`

人类可读模式至少应展示：
- 输入 draft 文件路径
- draft 的 `instruction`
- 生成的 `task_id`
- 完整 `task_document`
- `lint_result` 的状态和摘要

`--json` 模式则应输出一个稳定对象，至少包含：
- `draft`
- `task_document`
- `lint_result`

选择原因：
- 这样既保留 smoke 的可读性，也让自动测试能围绕结构做断言
- 把输入 draft 一起回显进 JSON，有助于复盘“这个 DSL 是由哪份 TaskDraft 生成的”

替代方案：
- 只打印 `task_document`
- 只打印 lint 结论，不打印 DSL

未选择原因：
- 不能满足“检查输出的 dsl”这个核心目标

## 风险 / 权衡

- [风险] 真实 smoke 依赖模型和配置，可重复性弱于 fake 测试
  - 缓解措施：自动测试只验证脚本协议，并通过 patch `DslNode.run` 固定结构，不对真实生成内容做快照断言。

- [风险] 默认样例位于 `output/`，可能被人工覆盖
  - 缓解措施：脚本允许显式传入其他 draft 文件；设计上把 `output/test_task_draft.json` 视为默认样例，而不是唯一真相。

- [风险] Fireball 类样例较复杂，人工输出可能较长
  - 缓解措施：人类可读模式先打印高层摘要，再输出格式化后的 `task_document` 和 lint 结果。

## Migration Plan

1. 新增 `src/smoke/test_dsl.py`，提供默认 draft 文件、`--config` 与 `--json` 等参数。
2. 在脚本中读取 `TaskDraft` JSON，校验并构造真实 `DslNode`。
3. 输出 `task_document` 与 `lint_result` 的人类可读摘要和 JSON 结构。
4. 在 `src/tests/test_smoke_scripts.py` 中增加最小自动测试，覆盖默认输入读取、JSON 输出和人类可读摘要。

## Open Questions

- 人类可读模式里是否还需要额外打印输入 draft 的 `judgments` / `missing_info` 摘要，便于对照翻译质量？
- 默认样例未来是否应该迁移到更稳定的 fixture 目录，而不是继续放在 `output/`？
