## 1. 主 agent 运行时骨架

- [x] 1.1 定义主 agent 的公共入口与结构化返回类型，明确取代旧 planner workflow 的对外调用面
- [x] 1.2 实现 `list_skills`、`load_skills`、`delegate` 三个主 agent 工具的最小可运行骨架
- [x] 1.3 定义主 agent 与子 agent 之间使用的 `ContextBundle`、`ResolutionBundle` 或等价数据契约

## 2. 子 agent 与工具边界

- [x] 2.1 实现 Context Agent profile，并将其默认工具边界收敛为 `grep` 与 `search`
- [x] 2.2 实现 Resolution Agent profile，并将其默认工具边界收敛为 `lint` 与新的 `execute`
- [x] 2.3 将现有 engine 执行链路包装为 `execute` 工具，并稳定返回执行报告与状态变化
- [x] 2.4 接通主 agent 到 Context Agent、Resolution Agent 的默认委派链路

## 3. 入口迁移与旧架构退场

- [x] 3.1 将 `augury.agent` 对外 planner 入口切换到主 agent 委派运行时
- [x] 3.2 迁移或删除旧的 `task_node`、`dsl_node`、固定 workflow 装配代码，消除它们作为长期真相的地位
- [x] 3.3 调整相关测试以覆盖新主流程、子 agent 委派和结构化结果契约

## 4. 删除 smoke 与收口验证

- [x] 4.1 删除 `src/smoke/` 下现有 smoke 入口及其相关依赖
- [x] 4.2 移除测试和文档中对 smoke 脚本作为长期入口的依赖
- [x] 4.3 用 `src/tests/` 与固定 eval fixtures 补齐 search、grep、planner、resolution 和端到端回归验证
- [x] 4.4 运行并收口新的自动测试与评测入口，确认项目不再依赖 smoke 目录
