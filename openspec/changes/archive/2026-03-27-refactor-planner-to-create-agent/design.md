## 上下文

当前 planner 虽然只使用 `search`、`fetch_keys`、`reads` 和 `lint` 这几类工具，并以 `PlannerResult` 作为唯一结构化输出目标，但默认运行时仍然通过 `deepagents.create_deep_agent()` 创建。该封装会自动带入面向通用 coding agent 的基础 prompt 和 middleware 组合，例如待办清单、文件系统、子代理、补丁工具与总结逻辑。这些能力并不是 planner 生成 `TaskDocument` 的必要条件，却会显著放大 prompt 体积与运行时行为复杂度。

与此同时，planner 已经在更高一层自己承担了：

- 请求与结果的结构化模型
- `ToolStrategy(PlannerResult)` 约束
- 本地 schema/执行器双层校验
- 可选 HITL/checkpointer
- 文件日志与 smoke 调试链路

这意味着 planner 的真正需求更接近“一个轻量的工具型 agent”，而不是“通用 deep coding agent”。因此这次变更把 runtime 收敛到 `langchain.agents.create_agent()`，只保留 planner 真实依赖的那部分能力。

## 目标 / 非目标

**目标：**
- 将 planner 默认运行时从 `create_deep_agent()` 重构为 `create_agent()`。
- 在不改变 planner 对外契约的前提下，保留结构化输出、HITL、checkpointer、日志和 smoke 行为。
- 去掉 deep agent 默认 coding-agent prompt 与 middleware 带来的额外 token 负担和行为噪音。
- 为后续如需拆分为显式 LangGraph 节点的 planner 留出更清晰的演进路径。

**非目标：**
- 不在本次变更中直接把 planner 重写为完全手写的多节点 LangGraph 工作流。
- 不在本次变更中改变 `PlannerRequest`、`PlannerResult`、`TaskDocument` 或 `ready / needs_human / blocked` 三态契约。
- 不在本次变更中重新设计 planner prompt、工具预算策略或 world state 表示层。
- 不在本次变更中新增 planner 业务工具或改变既有 `search` / `fetch_keys` / `reads` / `lint` 的职责边界。

## 决策

### 决策: planner 默认 runtime 改为直接使用 `langchain.agents.create_agent()`

planner factory 将直接使用 `langchain.agents.create_agent()` 创建运行图，而不是继续通过 `deepagents.create_deep_agent()` 这一层包装。这样可以保留 LangChain/LangGraph agent 的主流程能力，同时避免继承 deep agent 的通用 coding-agent 默认配置。

考虑过的替代方案：
- 继续使用 `create_deep_agent()`，只尝试关闭部分 middleware：能减少一部分开销，但仍然耦合到 deep agent 的默认 prompt 和包装语义，难以彻底收敛。
- 直接手写多节点 LangGraph：长期最灵活，但本次目标是先做低风险减法，不把重构面一次拉得过大。

### 决策: 保持 planner 对外契约不变，只替换底层 agent factory

本次变更不会改变调用方如何创建或消费 planner。`create_planner(...)` 仍然是统一入口，`PlannerResult` 仍然是唯一结构化返回模型，planner 的 schema 校验、执行器语义校验、日志和 smoke 路径都保持现有语义。

这样可以把这次重构收敛为“runtime 替换”，避免让调用方同时承担 API 迁移成本。

考虑过的替代方案：
- 同时修改 planner 请求/响应结构：能够顺手做更多清理，但风险更高，且与当前 token/行为问题不是同一个层面。

### 决策: 仅保留 planner 真正需要的 middleware/HITL 能力

`create_agent()` 版本的 planner 将只保留 planner 明确需要的能力：

- 工具列表：`search`、`fetch_keys`、`reads`、`lint`
- `ToolStrategy(PlannerResult)` 结构化输出
- `interrupt_on` 对应的 HITL middleware 或等价中断语义
- `checkpointer` 支持的同线程恢复能力

deep agent 默认附带的待办清单、文件系统、子代理、补丁工具、总结与 provider 特定缓存中间件，不应继续作为 planner 默认运行时的一部分。

考虑过的替代方案：
- 把 deep agent 的 middleware 原样搬到 `create_agent()` 上：技术上可行，但会保留 planner 当前最想摆脱的开销和噪音。

### 决策: 保留 `ToolStrategy(PlannerResult)`，不在本次重构中改动结构化输出策略

planner 最近已经显式切换为 `ToolStrategy(PlannerResult)`，以避免第三方 OpenAI-compatible 网关上的 provider-native structured output 不稳定问题。本次 runtime 重构不改变这一点，而是继续沿用同一结构化输出策略，避免把两个变量同时改掉。

考虑过的替代方案：
- 借这次重构同时切回自动策略或 provider strategy：会放大排障面，不利于判断 runtime 重构本身是否改善效果。

### 决策: 继续保留 planner 对 LangGraph checkpoint/resume 语义的兼容支持

当前 planner 已经通过 `interrupt_on` 与内存 checkpointer 支持 HITL 恢复。本次需要确认 `create_agent()` 路径下仍然可以保持同等语义，包括：

- 配置了 `interrupt_on` 时仍然可以创建默认内存 checkpointer
- smoke/调试入口仍然可以用同一 `thread_id` 继续运行
- planner 在 resume 场景下的日志和结果结构保持兼容

考虑过的替代方案：
- 在本次重构中暂时移除 HITL/checkpointer：实现更简单，但会破坏现有 smoke 体验和规范要求。

## 风险 / 权衡

- [`create_agent()` 下的中断/HITL 接线方式与 `create_deep_agent()` 有细节差异] → 通过保留专门测试覆盖 factory、resume 和 smoke 流程来锁定兼容行为。
- [移除 deep agent 默认 prompt 后，planner 行为可能发生轻微变化] → 保持现有 planner prompt 模板、工具集合和结构化输出策略不变，把行为变化收敛到 runtime 负担减少这一个维度。
- [未来仍可能需要更强的流程控制] → 本次只做“减法式重构”，后续如需 gather/draft/validate 拆节点，再基于更轻的 `create_agent()` 基线继续演进。
- [对 `deepagents` 的依赖变化可能影响已有测试或导入路径] → 更新对应测试断言，明确 planner 的默认 runtime 依赖已切换到 `langchain.agents.create_agent()`。

## Migration Plan

1. 在 planner factory 中移除默认 `deepagents.create_deep_agent()` 加载逻辑，改为解析并调用 `langchain.agents.create_agent()`。
2. 保留当前工具列表、`ToolStrategy(PlannerResult)`、checkpointer 与 `interrupt_on` 语义，补齐 `create_agent()` 路径所需的 middleware 接线。
3. 更新 planner 相关测试，覆盖默认 factory、结构化输出策略和 HITL/checkpointer 行为。
4. 运行 planner/smoke 相关测试，确认对外契约和调试链路未回退。

## Open Questions

- `interrupt_on` 是否应继续直接透传给 `create_agent()` 的 middleware/interrupt 接口，还是在 planner 内部进一步包装为更显式的 HITL middleware 构造过程？
- 完成本次 runtime 收敛后，是否需要下一步单独提出 change，把 planner 再拆成更显式的 LangGraph gather/draft/validate 工作流？
