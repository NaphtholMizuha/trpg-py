## 1. grep 工具实现

- [x] 1.1 在 `trpg_py.agent.tools` 中新增 `grep` 工具的输入输出模型、核心匹配逻辑与 LangChain tool 封装
- [x] 1.2 实现基于 canonical 叶子点路径的关键词模糊匹配、排序和匹配原因生成，并保持 `ok/no_match/error` 结构化语义
- [x] 1.3 为 `grep` 工具补充 `loguru` 输入输出日志与模块导出入口

## 2. Planner 集成

- [x] 2.1 将 `grep` 接入 planner 默认工具集与 factory 组装链路，确保调用方可通过默认 `create_planner(...)` 获得该工具
- [x] 2.2 更新 planner prompt 与状态取证策略，明确优先采用 `grep -> read`，并将 `list` 降为补充导航工具
- [x] 2.3 调整 planner 相关测试，覆盖 `grep` 命中、`grep` 无命中回退 `list`、以及候选路径批量 `read` 收口的行为

## 3. 验证与 Smoke

- [x] 3.1 新增 `smoke/test_grep.py`，展示 `grep` 的命中、无命中和错误边界
- [x] 3.2 更新 planner smoke 或调试链路，帮助开发者观察加入 `grep` 后的工具调用轨迹与预算表现
- [x] 3.3 运行相关 smoke/测试并确认新增 `grep` 工具不会破坏现有 `list`、`read` 与 planner 的既有契约
