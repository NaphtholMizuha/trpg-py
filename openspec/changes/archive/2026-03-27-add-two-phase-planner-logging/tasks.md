## 1. 第一阶段基础日志

- [x] 1.1 设计并实现 planner run 级日志文件路径与 run 标识生成逻辑，确保每次规划都会在 `logs/planner/` 下生成独立日志文件
- [x] 1.2 在 `trpg_py.agent.planner` 中补充基础日志事件，覆盖请求入口、轮次边界、最终状态以及 blocked 异常摘要
- [x] 1.3 为结构化输出失败等关键 blocked 场景增加专门日志记录，保留 schema/tool 名称、底层异常来源和 AI 响应摘要
- [x] 1.4 为第一阶段日志能力补充单元测试，覆盖日志文件生成和 blocked 诊断信息落盘

## 2. 第二阶段扩展快照

- [x] 2.1 扩展 planner 文件日志，记录 prompt/response 摘要、validation feedback、结构化响应快照和修复轨迹
- [x] 2.2 将工具调用摘要与 planner run/round 上下文关联起来，确保开发者能从单次日志文件复盘完整规划过程
- [x] 2.3 为第二阶段扩展日志补充测试，覆盖修复轮、结构化响应快照和多轮规划场景

## 3. Smoke 与文档接线

- [x] 3.1 更新 `smoke/test_planner.py`，在保持默认高可读摘要的前提下提示本次 planner 日志文件路径或等价定位信息
- [x] 3.2 更新 `smoke/test_planner_engine.py`，在 blocked 场景下提示本次 planner 日志文件路径或等价定位信息
- [x] 3.3 补充 smoke 脚本测试与 README 说明，覆盖日志路径提示和 planner 文件日志的调试用法
