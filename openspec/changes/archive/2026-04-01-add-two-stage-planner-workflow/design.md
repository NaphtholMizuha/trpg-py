## 上下文

当前 `src/augury/planner/` 下已经有 `tools/`、`task_document.py` 和运行时支撑文件，但还没有新的 planner workflow 主入口。用户现在要开始实现新的 planner，并且已经明确了目录约束：
- workflow 放在 `planner` 文件夹里面
- 两阶段 ReAct 节点放在 `planner/nodes/`
- 两个阶段必须拆成两个文件

这意味着这次设计的核心不是单个节点 prompt，而是先把 planner 的代码组织方式和职责分层定清楚。否则实现时很容易再次出现 workflow、节点逻辑、工具调用约束和类型定义互相缠绕的问题。

## 目标 / 非目标

**目标：**
- 在 `src/augury/planner/` 下建立新的 workflow 入口文件，作为 planner 的唯一编排真相。
- 在 `src/augury/planner/nodes/` 下建立两个独立节点文件，分别实现第一阶段和第二阶段的 ReAct 节点。
- 明确第一阶段负责把 DM 指令整理为半结构化任务概述，第二阶段负责把该概述翻译为 TaskDocument DSL。
- 明确 workflow、nodes、task document、runtime guards 与 tools 的依赖方向，避免循环引用和职责污染。
- 为后续实现保留清晰扩展点，例如后续新增第三阶段 verifier 或替换 workflow 编排方式。

**非目标：**
- 本次设计不重新定义 planner 所有 prompt 文案细节。
- 本次设计不扩展新的 tool 协议；现有 `planner/tools/` 仍是下游依赖。
- 本次设计不在 workflow 外再引入新的并行编排框架层。
- 本次设计不要求一次性实现完整 planner 业务语义，只先建立稳定骨架和节点边界。

## 决策

### 决策 1：workflow 入口放在 `src/augury/planner/` 根下

新的 planner workflow 入口文件直接放在 `src/augury/planner/` 根目录，例如 `workflow.py` 或同等单一入口模块。这个文件负责：
- 定义 planner 总体状态
- 串联两阶段节点
- 管理节点之间的数据流和最终输出

这样做的原因是，workflow 属于编排层真相，不应下沉到 `nodes/` 或 `tools/`。放在 planner 根下可以让调用方更容易发现主入口，也能让 nodes 保持纯节点职责。

考虑过的替代方案：
- 把 workflow 也放到 `nodes/`：会混淆“节点实现”和“状态机编排”。
- 把 workflow 单独放到仓库其他目录：会削弱 planner 目录内部的局部一致性。

### 决策 2：两阶段 ReAct 节点在 `src/augury/planner/nodes/` 下拆成两个文件

在 `src/augury/planner/nodes/` 下新增两个独立模块，例如：
- `intent_node.py`
- `dsl_node.py`

第一阶段节点负责：
- 消费 DM 指令
- 调用合适工具获取上下文
- 产出半结构化任务概述

第二阶段节点负责：
- 消费半结构化任务概述
- 翻译为 TaskDocument DSL
- 执行 lint/修复闭环

这样做的原因是，这两个阶段天然对应不同的输入、输出和工具访问模式。拆到两个文件后，后续测试、替换和独立迭代都会更简单。

考虑过的替代方案：
- 把两个节点写在一个 `nodes.py`：短期省文件，长期会迅速回到旧的“大文件多职责”问题。
- 每个节点再拆多层子文件：在当前阶段过早复杂化。

### 决策 3：workflow 只编排，不承载节点内部工具策略

workflow 层只关心：
- 起始输入
- 节点调用顺序
- 状态对象
- 成功/失败/needs_human 等流程分支

节点内部的工具访问策略、结构化输出约束和局部修复循环，留在各自节点文件中实现。

这样做的原因是，workflow 如果同时知道太多节点细节，会让节点失去独立性，也会使后续替换节点实现时需要修改编排层。

### 决策 4：节点之间通过明确的中间对象传递，而不是共享自由文本

第一阶段和第二阶段之间必须有一个明确的中间对象，例如 `TaskBrief` 或同等半结构化 planner 中间表示。workflow 负责传递该对象，第二阶段不得重新把第一阶段输出当成无限自由文本重新理解。

这样做的原因是，两阶段架构的价值就在于“先理解任务，再翻译 DSL”。如果中间层仍是松散文本，第二阶段会重新承担第一阶段的职责，架构收益会丢失。

## 风险 / 权衡

- [目录骨架先行，具体节点协议仍可能调整] → 通过在规范里只锁定职责和目录边界，不过早冻结每个字段细节。
- [两阶段拆文件会引入更多模块] → 这是有意的复杂度，用来换取可维护的职责边界。
- [workflow 与节点状态对象可能在早期重复定义] → 通过要求中间对象集中落在 planner 目录的共享类型模块中，减少分散定义。
- [后续可能需要第三阶段 verifier] → 当前 workflow 先只定义两阶段主干，但保持节点可扩展，后续可自然插入 verifier。

## Migration Plan

1. 先在 `src/augury/planner/` 下建立 workflow 入口和 `nodes/` 目录。
2. 新建第一阶段节点文件，实现 DM 指令到半结构化任务概述的最小闭环。
3. 新建第二阶段节点文件，实现任务概述到 TaskDocument DSL 的最小闭环。
4. 将 workflow 与共享类型、runtime guard、tools 串接起来，并补最小测试或 smoke 验证。

## Open Questions

- workflow 入口文件最终命名是 `workflow.py`、`planner.py` 还是其他名称？本设计默认使用 `workflow.py` 作为更清晰的编排命名。
- 第一阶段到第二阶段的中间对象是否直接命名为 `TaskBrief`，还是沿用现有 `task_document.py` 中更贴近 DSL 的命名？本设计建议使用独立的中间对象名称，避免与最终 DSL 混淆。
