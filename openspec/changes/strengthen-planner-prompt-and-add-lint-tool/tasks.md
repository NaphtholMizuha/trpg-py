## 1. Prompt DSL Teaching

- [x] 1.1 更新 planner 的 system/user prompt 模板，显式加入 `TaskDocument` 最小骨架、合法 `type/kind` 组合、引用约定和至少一个 canonical example
- [x] 1.2 为增强后的 prompt 增加或更新测试，覆盖 planner 面对攻击类指令时不会再用 `action/actor` 等自由字段替代 DSL 字段

## 2. Lint Tool

- [x] 2.1 在 `trpg_py.agent.tools` 中新增名为 `lint` 的只读工具，并复用现有 `TaskDocumentSchema` 与执行器校验链路
- [x] 2.2 为 `lint` 工具定义结构化输入输出，稳定区分合法、非法和工具错误，并返回可定位字段路径的错误详情
- [x] 2.3 为 `lint` 工具补充单元测试，覆盖合法文档、字段缺失、语义非法和异常场景

## 3. Planner Integration And Verification

- [x] 3.1 将 `lint` 接入 planner 默认工具集和提示词策略，使 planner 在准备返回 `ready` 前可以用 `lint` 收口候选文档
- [x] 3.2 保留并验证现有最终 Schema + 执行器兜底校验，确保 `lint` 不替代最终守门
- [x] 3.3 更新 planner/smoke/README 相关测试或说明，帮助开发者观察 prompt 增强与 `lint` 自检后的效果
