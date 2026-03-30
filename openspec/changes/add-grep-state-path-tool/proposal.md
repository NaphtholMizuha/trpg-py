## 为什么

当前 planner 在状态取证阶段过度依赖 `list(prefix)` 和精确 `read(paths)` 组合来发现可引用状态路径，但模型往往只知道“想找什么字段”，并不知道 canonical 点路径该如何命名。这会导致 planner 围绕近似前缀和候选路径反复试探，放大工具调用次数，并更容易耗尽单轮工具预算。

## 变更内容

- 新增一个面向 planner 的 `grep` 风格状态路径检索工具，允许模型输入一组关键词并返回按相关性排序的叶子点路径候选，而不要求模型先猜出正确前缀。
- 将 planner 的状态发现策略改为优先使用 `grep` 缩小候选路径集合，再使用批量 `read` 一次性确认值；`list` 继续保留为补充型导航工具，而不是默认主路径发现工具。
- 为新工具增加结构化返回语义、运行日志和 smoke 验证入口，确保调用方可以稳定区分命中、无命中和错误，并据此驱动 planner 分支决策。

## 功能 (Capabilities)

### 新增功能
- `grep-tool`: 提供基于关键词的模糊叶子路径检索能力，返回排序后的 canonical 点路径候选及其匹配依据，供 planner 和其他 agent 做状态路径发现。

### 修改功能
- `agent-planner`: 调整 planner 的状态取证策略，使其优先使用 `grep` 做模糊路径发现，并在获得候选后优先批量 `read` 收口，而不是围绕 `list`/`read` 反复试探。

## 影响

- 受影响代码：`trpg_py.agent.tools` 下新增 grep 工具实现与导出；`trpg_py.agent.planner` 的默认工具集、prompt 约束和证据获取流程；对应 smoke 与测试代码。
- 受影响规范：新增 `specs/grep-tool/spec.md`；修改 `specs/agent-planner/spec.md`。
- 预期结果：减少 planner 因状态路径发现不精准导致的工具往返，提升预算利用率，同时保持现有 `list`、`read` 和 `lint` 的职责边界不变。
