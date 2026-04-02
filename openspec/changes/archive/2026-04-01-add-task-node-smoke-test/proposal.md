## 为什么

现在虽然已经有 `task_node` 的自动测试，但还缺一个开发者可以手动运行的 smoke 脚本，专门观察它把 DM 指令翻译为 `TaskDraft` 的结果。随着 planner 进入两阶段设计，第一阶段任务稿的质量会频繁调整，现在需要一个更直观的入口来验证 prompt、tools 和结构化输出是否仍然正常工作。

## 变更内容

- 新增一个 `src/smoke/test_task.py` 脚本，专门验证 `task_node` 将一条指令翻译为 `TaskDraft` 的能力。
- 让该脚本支持从默认 world state 或显式指定的 state 文件加载状态，并允许传入自定义 instruction。
- 让该脚本输出适合人工检查的结果，包括 `task`、`reads`、`judgments`、`writes`、`missing_info` 等 `TaskDraft` 关键字段。
- 为该 smoke 脚本补充最小自动验证，确保脚本入口和基本输出格式不会在后续重构中悄悄失效。

## 功能 (Capabilities)

### 新增功能
- `planner-task-smoke-test`: 定义一个专门验证 `task_node` 将 DM 指令翻译为 `TaskDraft` 的手动 smoke 脚本及其可观察输出。

### 修改功能
- `smoke-test-layout`: 扩展 smoke 目录的约束，要求 `task_node` 的手动验证脚本以一致的 smoke 入口形式提供。

## 影响

- 受影响代码：`src/smoke/` 下会新增 `test_task.py`，并可能补充对应测试。
- 受影响 planner 代码：`task_node` 的调用方式和 `TaskDraft` 关键字段会成为 smoke 输出契约的一部分。
- 受影响开发流程：调试第一阶段任务稿时将有一个稳定的手动验证入口，而不必只依赖自动测试或临时脚本。
