## 1. Smoke Script Scaffold

- [x] 1.1 在 `smoke/` 下新增 planner+engine 端到端烟雾测试脚本，复用现有 planner 配置与 world state 加载链路
- [x] 1.2 为新脚本加入 CLI 参数，至少覆盖 instruction、config、JSON 输出以及可控骰子来源
- [x] 1.3 设计新脚本的默认终端展示结构，必要时接入 `rich` 或配套展示辅助，让测试员能快速看懂当前阶段与结果

## 2. Planner To Engine Execution

- [x] 2.1 实现脚本主链路：调用 planner，在 `status=ready` 时把 `task_document` 交给 engine 执行
- [x] 2.2 复用或接入 planner smoke 的 HITL 输入与 resume 机制，使 `needs_human` 时可以收集测试员输入并继续规划
- [x] 2.3 为脚本补充高可读性的人类可读摘要与 JSON 输出，区分 planner 阶段结果、execution 状态和最终已应用变更
- [x] 2.4 处理 `blocked` 与测试员主动退出分支，确保这些状态下不会继续调用 engine
- [x] 2.5 如引入 `loguru` 或 `rich`，将其限定在 smoke 展示/诊断层，避免侵入 planner 或 engine 核心逻辑

## 3. Automated Coverage

- [x] 3.1 为新脚本补自动测试，覆盖 ready 后执行成功并输出状态变更摘要
- [x] 3.2 为新脚本补自动测试，覆盖 planner 返回 `needs_human` 后收集测试员输入并恢复到 `ready`
- [x] 3.3 为新脚本补自动测试，覆盖 planner 返回 `blocked` 或测试员退出时停止执行 engine
- [x] 3.4 为新脚本补自动测试，覆盖 JSON 输出中同时包含 planner 阶段结果与 execution 阶段结果
- [x] 3.5 为新脚本补自动测试，覆盖默认终端输出能清晰展示阶段分段与关键状态变化
