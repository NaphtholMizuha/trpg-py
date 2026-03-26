## 为什么

当前仓库已经分别有 `smoke/test_planner.py` 和 `smoke/test_engine.py`，但它们只覆盖了“planner 产出什么”和“engine 如何执行既有 TaskDocument”两个分段视角，缺少一个从 DM 指令出发，贯通 planner 到 engine 并直接观察最终 state 变化的端到端烟雾测试入口。

这个入口现在值得补，因为 planner、reads、lint 和 smoke world state 最近都在持续演化。没有一条稳定的 instruction-to-state 验证链路时，我们很难快速判断问题是出在规划阶段、执行阶段，还是两者交界处。

## 变更内容

- 新增一个端到端 smoke 测试入口，把 planner 产出的 `TaskDocument` 直接交给 engine 执行，展示从 instruction 到最终状态变更的完整链路。
- 让该 smoke 脚本支持以真实 planner 配置、真实 world state 和可控骰子来源运行，而不是要求开发者手工在 `test_planner` 和 `test_engine` 之间搬运中间结果。
- 让该 smoke 脚本的人类可读输出更适合测试员直接观察，必要时使用 `rich` 或 `loguru` 改善阶段分段、状态摘要和变更展示效果。
- 为该脚本补充自动测试，覆盖成功规划并执行、`needs_human` 时收集测试员输入并继续规划、以及执行后输出状态变更摘要等核心场景。
- 保持现有 `smoke/test_planner.py` 与 `smoke/test_engine.py` 的分工不变，新脚本作为两者之间的集成验证入口存在。

## 功能 (Capabilities)

### 新增功能
- `planner-execution-smoke`: 提供一个手动可运行的端到端 smoke 入口，用于验证 DM 指令经过 planner 规划后再交由 engine 执行时的最终状态变化效果。

### 修改功能

## 影响

- `smoke/` 下新增 planner+engine 端到端脚本，可能复用 `test_planner.py` / `test_engine.py` 的部分加载与输出逻辑
- `tests/test_smoke_scripts.py` 或新增测试文件，用于覆盖该端到端 smoke 入口
- 可能涉及 `trpg_py.agent`、`trpg_py.engine` 的轻量拼装辅助，但不改变核心 planner 或 executor 契约
