## 新增需求

## 修改需求

### 需求:smoke 目录必须为 dsl_node 提供独立的手动验证入口
系统必须在 `src/smoke/` 目录下为 `dsl_node` 提供独立的手动验证脚本入口，禁止要求开发者只能通过自动测试、临时 Python 片段或完整 planner workflow 才能观察 `TaskDraft -> TaskDocument` 的翻译结果。

#### 场景:开发者单独验证 dsl_node 输出
- **当** 开发者需要检查一份现成 `TaskDraft` 会被 `dsl_node` 翻译成什么 `TaskDocument`
- **那么** 可以直接在 `src/smoke/` 下找到独立的 `dsl_node` smoke 入口
- **那么** 该入口必须与其他 smoke 脚本保持一致的目录语义

#### 场景:开发者观察 dsl_node repair 回路
- **当** `dsl_node` smoke 入口在首轮生成后进入 lint-repair 回路
- **那么** 脚本输出必须能让开发者观察是否触发了 repair
- **那么** 脚本输出必须能让开发者观察最终轮次和最终 lint 结论

#### 场景:开发者观察 dsl 到 engine 的执行结果
- **当** `src/smoke/test_dsl.py` 生成的 `lint_result.status` 为 `valid`
- **那么** 脚本输出必须继续展示执行阶段结果
- **那么** 脚本输出必须继续展示关键 state 变化摘要，而不只是停在 DSL 与 lint

## 移除需求
