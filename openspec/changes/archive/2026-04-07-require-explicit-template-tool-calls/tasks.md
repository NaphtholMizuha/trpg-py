## 1. Dsl Node 工具边界收紧

- [x] 1.1 删除 `dsl_node` 中对 `template` 的宿主侧预取逻辑，以及对应的 `template_query_hint` / `template_lookup` prompt 注入
- [x] 1.2 保留 `template` 与 `lint` 在 `dsl_node` 默认工具集合中的挂载，并确保模板查询只能由 agent 在运行时显式触发
- [x] 1.3 调整 `dsl_node` 相关 smoke 或 workflow 代码，避免继续依赖宿主预取结果

## 2. Prompt 与工具可观测性

- [x] 2.1 更新 `planner_dsl_node_system.txt`，要求模型先显式调用 `template`，再生成候选 DSL 并调用 `lint`
- [x] 2.2 更新 `planner_dsl_node_user.txt`，移除宿主注入模板结果字段，并保留受控枚举调用约束
- [x] 2.3 为 `template` 工具增加输入/输出日志或等价诊断信息，至少可观察查询字段、命中状态、模板 ID 与回退状态

## 3. 验证

- [x] 3.1 增加自动测试，验证 `dsl_node` 不再预取 `template`，而是把它作为真实 agent 工具暴露
- [x] 3.2 增加自动测试，验证默认 prompt 不再依赖 `template_query_hint` / `template_lookup` 注入字段
- [x] 3.3 增加 workflow 或 smoke 验证，证明真实运行中可以观察到 `template` 工具调用痕迹，并且它与 `lint` 共同参与 DSL 生成链路
