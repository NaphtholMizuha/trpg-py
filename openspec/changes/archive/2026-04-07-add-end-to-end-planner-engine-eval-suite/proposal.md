## 为什么

当前仓库已经有单点 smoke 和若干单元测试，但还缺少一套稳定、可重复、可比较的端到端评测基线。每次我们调整 `task_node`、`dsl_node` prompt 或 workflow 时，很难用同一组世界状态和同一批用户输入判断“整体链路到底变好了还是退化了”。

## 变更内容

- 新增一套专门用于 planner -> engine 全链路评测的固定世界状态 fixture。
- 新增 10 条覆盖直接攻击、范围法术、治疗、资源消耗、纯查询、缺信息等场景的黄金用户输入。
- 新增一个端到端评测入口，逐条运行 instruction -> `TaskDraft` -> `TaskDocument` -> engine execution 的完整流程。
- 为每个案例记录中间产物和评测结果，包括 `TaskDraft`、`lint_result`、`TaskDocument`、执行结果、状态变更和失败原因。
- 定义自动评估摘要，让调用方可以快速看到每条案例的通过/失败、缺口分类和回归风险。

## 功能 (Capabilities)

### 新增功能
- `planner-e2e-eval-suite`: 提供固定世界状态、10 条端到端案例、逐案例日志和自动评估汇总，用于验证 planner 到 engine 的完整链路。

### 修改功能
- 无

## 影响

- `src/smoke/` 下的端到端评测入口与辅助模块
- 评测用 fixture、案例清单和日志输出目录
- `src/tests/` 中覆盖评测入口、日志格式和汇总逻辑的自动测试
- 与 planner workflow、`task_node`、`dsl_node`、engine 执行链路联动的回归验证方式
