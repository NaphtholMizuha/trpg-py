## 1. Reads Tool

- [x] 1.1 在 `trpg_py.agent.tools` 中新增 `reads` 工具，并复用底层 `state-store.reads` 语义读取点路径值
- [x] 1.2 为 `reads` 设计结构化输入输出，稳定区分命中、无命中和错误，并返回逐路径读取结果
- [x] 1.3 为 `reads` 补充单元测试，覆盖命中、无命中、路径错误和日志行为

## 2. Planner Integration

- [x] 2.1 将 `reads` 接入 planner 默认工具集与 prompt/策略，使 planner 可在实体解析和关键参数确认时使用它
- [x] 2.2 增加或更新 planner 测试，覆盖 state 中已有 actor id 或关键值时不再过早进入 HITL

## 3. Smoke And Docs

- [x] 3.1 新增 `smoke/test_reads.py`，展示值读取、无命中和错误边界
- [x] 3.2 更新 smoke/README 相关说明，帮助开发者理解 `fetch_keys` 与 `reads` 的职责分工
