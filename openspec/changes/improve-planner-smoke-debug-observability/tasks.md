## 1. Planner 调试轨迹模型

- [x] 1.1 为 planner 设计可选 debug 负载结构，覆盖规划轮次、结构化响应摘要、修复反馈和最终失败原因
- [x] 1.2 在 `trpg_py/agent/planner.py` 中为多轮规划/修复流程累积调试轨迹，并在失败时保留最后一次校验上下文
- [x] 1.3 调整 `needs_human` 与 `blocked` 的解释信息，使调用方可以区分真实澄清与内部产物失败

## 2. Smoke 调试入口

- [x] 2.1 为 `smoke/test_planner.py` 增加显式 debug 开关，并支持在人类可读输出中展示调试轨迹摘要
- [x] 2.2 扩展 `smoke/test_planner.py` 的 JSON 输出，使其在 debug 模式下包含结构化调试负载
- [x] 2.3 优化 smoke 输出中的失败摘要，明确展示最后一次校验失败或依赖故障原因

## 3. 验证与回归

- [x] 3.1 为 planner 增加测试，覆盖普通成功路径、修复路径、修复失败路径和依赖故障路径下的 debug 负载
- [x] 3.2 为 smoke 脚本增加测试，覆盖 debug 开关的人类可读输出和 JSON 输出
- [x] 3.3 运行相关测试并记录任何仍未覆盖的 Deep Agents/外部依赖限制
