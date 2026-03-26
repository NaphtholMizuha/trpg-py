## 上下文

当前 planner 已经能通过 `search` 获取规则证据、通过 `fetch_keys` 发现状态路径，并通过 `lint` 检查候选 `TaskDocument`。但它仍然缺少“从已知路径读取当前值”的能力，因此当指令包含自然语言实体名、动态 AC、生命值、法术位或其他必须依赖 state 值确认的信息时，planner 只能依赖猜测或提前进入 HITL。

底层 `state-store` 已经提供 `reads` 能力，因此这次变更的重点不是新造一套路径读取语义，而是把它以 agent tool 的形式暴露给 planner，并在 prompt/策略层明确其使用场景。

## 目标 / 非目标

**目标：**
- 提供名为 `reads` 的 agent tool，复用底层 `state-store.reads` 读取点路径值。
- 让 `reads` 返回稳定的结构化结果，供 planner 区分“命中值”“路径不存在”“工具错误”。
- 让 planner 在实体解析和关键参数确认时优先使用 `fetch_keys + reads`，减少可避免的 HITL。
- 为 `reads` 提供 smoke 脚本和测试，便于开发者直接观察读取行为。

**非目标：**
- 不把 `reads` 扩展成模糊实体搜索器或自然语言别名解析器。
- 不允许 `reads` 写入状态、修改默认 world state 或替代执行器。
- 不改变既有 `ready/needs_human/blocked` 三态契约。

## 决策

### 决策 1：`reads` 只做点路径值读取，不承担模糊实体匹配

`reads` 的职责是“给定路径，返回当前值”；它不会直接接受“哥布林”或“艾尔德拉”这种自然语言短语做解析。planner 仍然需要先用 `fetch_keys` 缩小候选路径范围，再用 `reads` 读取候选值进行判断。

考虑过的替代方案：
- 直接做 `resolve_entity` 工具：更智能，但边界更大，也更容易把工具能力做成半套知识库。
- 在 `reads` 中加入模糊匹配：实现上更混乱，会让读取语义不再稳定。

### 决策 2：`reads` 复用 `state-store.reads`，不维护独立路径语义

`reads` 将复用底层状态存储包的路径读取与错误语义，确保 agent 工具层与执行器/引用解析层看到的是同一套状态真相。

考虑过的替代方案：
- 在工具层重新实现路径读取：短期可行，但长期会与 `state-store` 漂移。

### 决策 3：planner 采用 `fetch_keys -> reads -> lint` 的证据收口顺序

在需要读取 state 值的场景下，planner 的推荐顺序是：
1. 用 `fetch_keys` 找到可能相关的路径；
2. 用 `reads` 读取这些路径上的具体值；
3. 在产出候选 `TaskDocument` 后继续用 `lint` 收口。

这让各工具职责更清晰：`fetch_keys` 解决“哪里可能有值”，`reads` 解决“值到底是什么”，`lint` 解决“文档是否合法”。

考虑过的替代方案：
- 让 planner 直接大量盲读路径：会浪费工具预算，也更依赖 prompt 猜路径。
- 用 `reads` 替代 `fetch_keys`：如果路径本身未知，读值并不能帮 planner缩小搜索范围。

## 风险 / 权衡

- [planner 过度读取 state，导致工具预算膨胀] → 在 prompt 中明确 `reads` 只用于确认少量关键路径，而不是扫描整个状态树。
- [调用方误以为 `reads` 能做实体别名解析] → 在工具描述和 spec 中明确其边界是“路径读取”，不是“自然语言解析”。
- [工具层与底层路径语义不一致] → 要求 `reads` 直接复用 `state-store.reads`。

## 迁移计划

1. 先新增 `reads` 工具和结构化返回类型。
2. 再把它接入 planner 默认工具集和 prompt。
3. 最后补 smoke/test 和 README 说明，帮助开发者验证实体 ID 与关键值读取场景。

## 开放问题

- `reads` 的无命中结果应当是“整批 no_match”还是按路径逐项标注命中/无命中；倾向后者，因为更利于 planner 消费。
- planner 是否需要在 debug 输出中额外记录 `reads` 结果摘要，方便排查实体解析问题。
