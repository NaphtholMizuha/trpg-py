## 1. Interruptible Runtime

- [x] 1.1 设计并落地可中断工具的运行时数据结构，明确 pending interrupt、恢复输入和恢复后结果的边界
- [x] 1.2 在 agent runtime 中为 ask 接入 interrupt/resume 控制流，避免继续把 ask 只当作请求构造工具
- [x] 1.3 为 Python CLI 提供同步 facade，使 CLI 可以在同一次运行中收集回答并驱动恢复

## 2. Ask 与 Context Agent 行为升级

- [x] 2.1 将 ask tool 改为恢复后返回 `AskResponse` 的 interruptible tool，并保持统一宿主无关契约
- [x] 2.2 修改 Context Agent，使其在 ask 恢复后继续完成证据整理并生成更新后的 `ContextBundle`
- [x] 2.3 更新 planner 结果与相关提示/说明，明确区分 pending interrupt 与恢复后的最终结果

## 3. Eval 与验证

- [x] 3.1 更新 Context Agent eval 脚本，使其能观察 ask interrupt、在 CLI 中恢复并展示最终 bundle
- [x] 3.2 为 interrupt 触发、CLI 同步恢复和 ask 后继续生成结果补齐自动测试
- [x] 3.3 运行相关测试与手动 CLI 自检，确认 ask 在中断恢复后能继续产出最终结果
