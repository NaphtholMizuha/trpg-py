# Resolver 升级设计

## 目标

这份文档讨论如何把当前工作流中的“最小可运行 resolver”升级为真正可用的 `ResolverAgent`。

升级目标不是改变 `ResolutionWindow` / `ResolutionResult` 契约，而是提升 resolver 的裁决能力：

- 从“同路径覆盖”升级为“能理解同窗口内动作之间的语义关系”
- 从“只会处理字段冲突”升级为“能判断哪些 executor 结果整体失效、部分失效或仍然有效”
- 把 `triggered_chains` 的生成责任从 `executor` 迁移到 `resolver`
- 仍然坚持 resolver 只做同窗口内的合并裁决，不自动推进窗口外世界演化

## 当前版本的状态

当前 resolver 实现在 [nodes.py](/home/naifen/code/trpg-py/src/workflow/nodes.py#L154) 的 `_materialize_resolution`。

它的行为非常简单：

1. 按 `priority`、`order` 对 `window.runs` 排序
2. 逐个遍历所有 `field_changes`
3. 如果同一个 `path` 多次出现，则后处理的覆盖前处理的
4. 被覆盖的旧变更进入 `discarded_field_changes`
5. 最终产出 `ResolutionResult`

这个版本的优点是：

- 工作流已经跑通
- `resolver -> commiter` 的数据接口已经稳定
- 可以处理最基础的“同字段冲突”

它的缺点也很明显：

- 只懂 `path`，不懂动作语义
- 无法判断某个 run 是否整体失效
- 无法表达“护盾术使魔法飞弹伤害无效”这种跨字段、跨动作关系
- 无法对 `triggered_chains` 的有效性给出裁决

所以当前版本更准确地说，是一个“占位 resolver”。

## 升级方向

升级后的 resolver 应改为：

- 输入：完整 `ResolutionWindow`
- 输出：完整 `ResolutionResult`
- 执行方式：由 LLM 在结构化 schema 约束下做同窗口裁决

也就是说，未来真正的 resolver 不是一个纯函数 `_materialize_resolution(window)`，而是：

```python
resolution: ResolutionResult = resolver_agent.resolve(window)
```

其中 `_materialize_resolution` 可以保留为 fallback 或测试基线，但不再是主路径。

## 核心设计原则

- resolver 只读，不直接写 world-state
- resolver 不新增随机掷骰，除非未来明确扩展
- resolver 以 `ResolutionWindow` 为唯一主输入，不依赖隐藏上下文
- resolver 的输出必须始终落在 `ResolutionResult` 结构内
- resolver 要能解释“为什么丢弃某个字段变更”
- resolver 的判断对象应该是“run 之间的关系”，而不是只盯着字段 path

## 升级后 Resolver 要解决的问题

### 1. 语义级覆盖

例如：

- `魔法飞弹` 造成伤害
- `护盾术` 使其伤害无效

这里的问题不是单纯两个 run 都改了 `Aldera.combat.HP`。

更准确的语义是：

- `护盾术` 让主动作中的伤害结果失去效力
- 因此应该丢弃的是主动作中的伤害字段变更
- 而不是简单按谁最后写同一路径来覆盖

### 2. 动作整体失效

例如：

- `法术反制` 成功

它可能意味着：

- 某个施法动作对应的主要结果整体失效
- 该 run 中多个 `field_changes` 都不应生效

这时候 resolver 需要能做“按 run 或按 effect block”裁决，而不是只按单字段裁决。

### 3. 部分生效

有些 run 不是整体有效或整体无效，而是部分有效。

例如：

- 某个动作的伤害无效
- 但其资源消耗仍然生效

这意味着 resolver 需要支持：

- 保留某些字段变更
- 丢弃某些字段变更
- 对每条丢弃给出 reason

### 4. triggered_chains 的生成责任迁移

当前 `triggered_chains` 是 executor 直接产出的。

这在没有 resolver 的旧流程里还能成立，但在引入 `ResolutionWindow` 之后，问题会变得明显：

- executor 只能看到单步动作的局部结果
- 但某个后续 chain 是否应该存在，取决于该结果在当前 window 中最终是否成立
- 如果主动作后来被护盾术、法术反制或其他高优先级动作推翻，executor 预先生成的 chain 就可能成为脏数据

因此升级版设计明确改为：

- executor 不再负责“最终意义上的 triggered_chains 生成”
- resolver 才是 `triggered_chains` 的最终生成者

更准确地说：

- executor 最多只能提供“候选后续效果线索”
- resolver 在看完整个 `ResolutionWindow` 后，决定哪些 chain 最终成立

## 升级后的总体结构

建议新增一个 `ResolverAgent`，位置类似现有 `ExecutorAgent`：

- 文件建议：`src/agents/resolver.py`
- 对外方法：`resolve(window: ResolutionWindow) -> ResolutionResult`

工作流节点改造后：

1. `window_review` 把 `active_window.status` 设为 `ready`
2. `resolver` 节点读取 `active_window`
3. `resolver_agent.resolve(active_window)` 生成 `ResolutionResult`
4. `pending_resolution = resolution_result`
5. `commiter` 写入 `final_field_changes`
6. planner 或后续节点消费 resolver 最终确认的 chains

## ResolverAgent 输入

输入主对象仍然是 `ResolutionWindow`，包括：

- `window_id`
- `root_task_id`
- `root_description`
- `status`
- `shared_context`
- `runs`

其中最关键的是两部分：

- `shared_context`：当前窗口共享规则与状态背景
- `runs`：同窗口内多个 executor 结果及其 `priority/order`

resolver 必须把这两个部分一起看，而不是只看 `field_changes`。

## ResolverAgent 输出

### V2 推荐输出 Schema

既然 `triggered_chains` 的最终生成责任迁给 resolver，推荐把 `ResolutionResult` 扩展为：

- `final_field_changes`
- `discarded_field_changes`
- `final_triggered_chains`
- `discarded_triggered_chains`
- `resolution_summary`
- `dm_suggestions`

也就是说，升级后的 resolver 不只裁决字段，还裁决后续链条。

建议新增类型：

```python
class DiscardedTriggeredChain(TriggeredChain):
    reason: str
    discarded_by: str = ""
```

然后把 `ResolutionResult` 扩展为：

```python
class ResolutionResult(BaseModel):
    window_id: str
    final_field_changes: list[StateChange]
    discarded_field_changes: list[DiscardedStateChange]
    final_triggered_chains: list[TriggeredChain]
    discarded_triggered_chains: list[DiscardedTriggeredChain]
    resolution_summary: str
    dm_suggestions: list[str]
```

如果暂时不想立刻改代码，也可以先把这当作 V2 目标 schema。

其中 `discarded_field_changes.reason` 与 `discarded_triggered_chains.reason` 都要承担明确解释职责，例如：

- “护盾术使魔法飞弹伤害无效，因此该 HP 扣减不生效”
- “法术反制使该施法未成功完成，因此其后续效果不生效”
- “同一路径字段被更高优先级结果覆盖”

对于 chain 的 reason，可以是：

- “该 chain 依赖于主动作命中，但主动作最终未成立”
- “该 chain 依赖于法术成功施放，但施法被反制”

## Resolver 的推理对象

升级后的 resolver 不应只把每条 `field_changes` 当作独立原子项，也不应把 `triggered_chains` 当作 executor 已经决定好的最终结果。

更合理的理解层次是：

1. 先理解每个 run 在做什么
2. 再理解 run 之间的关系
3. 然后裁决哪些字段变更和哪些后续 chain 仍有效
4. 最后输出结构化结果

也就是说，resolver 的内部推理顺序应是：

- 先做动作级理解
- 再做效果级裁决
- 最后输出字段级结果

## 推荐的 Prompt 结构

建议为 resolver 增加独立 prompt 文件：

- `prompts/resolver.md`
- `prompts/force_output/resolver.txt`

系统提示应明确约束 resolver：

- 你只负责同窗口内的合并裁决
- 不要新增掷骰
- 不要自动推进窗口外场景
- 优先根据 `priority` 与 `order` 理解响应链
- 当某个 run 因更高优先级动作而整体失效时，应丢弃其相关字段变更
- 当某个 run 对应的后续链条依赖于已失效结果时，应丢弃其相关 triggered chains
- 当某个 run 只是部分失效时，只丢弃对应字段变更
- 当某个后续 chain 只在最终有效结果成立时才应出现，应由你决定是否放入 `final_triggered_chains`
- 输出必须符合 `ResolutionResult`

用户输入建议直接包含：

- `ResolutionWindow` 的 JSON
- 一段明确任务说明

例如：

```text
请合并以下 ResolutionWindow。
你的任务不是继续推进世界，而是只判断哪些 field_changes 在同一结算窗口内最终有效。
请严格输出 ResolutionResult。
```

## 建议使用的工具

升级后的 resolver 可以使用下列工具：

- `read`
- `search`
- `fetch_keys`

是否启用 `evaluate`：

- 默认不启用
- 只有当未来 resolver 需要做少量确定性数值整理时再考虑

原因是：

- resolver 的核心工作是语义裁决，不是随机结算
- 减少工具面可以降低误操作概率

## 与当前 `_materialize_resolution` 的关系

建议不要立刻删除 `_materialize_resolution`。

更合理的处理方式是：

- 把它降级为 fallback resolver
- 当 `ResolverAgent` 结构化输出失败时，再退回 `_materialize_resolution`

这样可以保证：

- 工作流始终可运行
- 即使 LLM 失败，系统仍有一个保底结果
- 方便对比“语义 resolver”和“路径覆盖 resolver”的效果差异

但要注意：

- `_materialize_resolution` 目前只会处理 `field_changes`
- 一旦 `ResolutionResult` 正式扩展了 chains 相关字段，fallback 也要给出空的 `final_triggered_chains` / `discarded_triggered_chains`

建议形态：

```python
try:
    resolution = resolver_agent.resolve(active_window)
except Exception:
    resolution = _materialize_resolution(active_window)
```

## 升级后的 Resolver 节点

升级后的 `resolver` 节点建议逻辑如下：

1. 读取 `active_window`
2. 校验 `active_window.status == ready`
3. 调用 `resolver_agent.resolve(active_window)`
4. 若失败则 fallback 到 `_materialize_resolution(active_window)`
5. 写入 `pending_resolution`
6. 将 `active_window.status = resolved`
7. `commiter` 写入字段
8. 后续节点消费 `final_triggered_chains`

这样节点职责会很清晰：

- 节点只负责调度与兜底
- Agent 负责裁决
- fallback 函数负责保底

## 为什么升级后仍保留 priority/order

即使换成 LLM resolver，`priority` 和 `order` 仍然是核心输入。

因为它们提供了两个不同维度的信息：

- `priority`：规则上的结算先后
- `order`：DM 实际追加动作的记录顺序

LLM 需要利用这两个信号来判断：

- 哪个响应在规则上先影响结果
- 哪个动作是后补入但优先级更高的

所以升级版 resolver 不是绕过这两个字段，而是更好地利用它们。

## 升级版的最小判断策略

为了避免第一次升级就过度复杂，建议 resolver 在 V2 先遵守以下简单原则：

1. 优先按 run 级理解动作关系
2. 当更高优先级 run 明确使较低优先级 run 失效时，丢弃其相关字段变更
3. 只有最终有效的结果才允许生成 `final_triggered_chains`
4. 若两个 run 没有明显语义冲突，再退回到字段级覆盖
5. 无法确定时，倾向于保守，并在 `dm_suggestions` 中提示 DM

这个策略比当前版本强很多，但仍然可控。

## 典型示例

### 示例 1：魔法飞弹 vs 护盾术

输入：

- run0：魔法飞弹，造成 HP 扣减
- run1：护盾术，说明其使魔法飞弹伤害无效

升级版 resolver 的理想输出：

- `final_field_changes`：
  只保留护盾术资源消耗
- `discarded_field_changes`：
  丢弃魔法飞弹导致的 HP 扣减
- `reason`：
  明确写“护盾术使魔法飞弹伤害无效”

### 示例 2：护盾术 vs 法术反制

输入：

- run0：主动作
- run1：护盾术
- run2：法术反制，针对护盾术

理想输出：

- 护盾术自身相关变更失效
- 主动作原本被护盾术抵消的效果重新有效
- 最终恢复主动作的伤害结果

这正是当前路径覆盖 resolver 做不到，但升级版应该处理的场景。

### 示例 3：依赖命中的后续 chain

输入：

- run0：攻击命中，并声称会触发一个后续附带效果 chain
- run1：更高优先级反应使攻击未命中或效果失效

理想输出：

- 与命中相关的字段结果失效
- 依赖“命中成立”的后续 chain 不进入 `final_triggered_chains`
- 对应 chain 进入 `discarded_triggered_chains`

## 失败模式与保守策略

升级后的 resolver 仍然可能失败，主要包括：

- LLM 结构化输出失败
- 理解不充分，无法确定某些冲突
- 输出字段遗漏

保守策略建议：

- 第一层：schema 校验失败则 fallback
- 第二层：输出为空或明显不完整则 fallback
- 第三层：对于无法确定的语义冲突，不要擅自推进窗口外后果，而是在 `dm_suggestions` 中提示

## 对测试的影响

升级 resolver 后，测试要分成两类：

### 1. 纯结构与 fallback 测试

继续保留当前的：

- `priority` 默认规则
- `ResolutionWindow` 收集逻辑
- `_materialize_resolution` 的确定性行为

### 2. ResolverAgent 行为测试

新增测试重点：

- 给定 window，resolver 是否返回合法 `ResolutionResult`
- 典型场景下是否丢弃正确的字段变更
- 当 agent 失败时是否正确 fallback

这里不一定一开始就做非常强的精确断言，但至少要锁定关键案例：

- 魔法飞弹 vs 护盾术
- 护盾术 vs 法术反制
- 同路径简单覆盖

## 分阶段落地建议

### Phase 1

- 保留当前 workflow 结构不变
- 新增 `ResolverAgent`
- `resolver` 节点改为优先调用 agent，失败时 fallback
- 先在代码中保留 executor 旧字段，但停止把 executor 的 chains 当作最终结果使用

### Phase 2

- 扩展 `ResolutionResult` schema，引入 `final_triggered_chains` 与 `discarded_triggered_chains`
- resolver 正式接管 chain 生成
- `commiter` 后的后续流程改为只消费 resolver 最终确认的 chains

### Phase 3

- 优化 prompt
- 增加更多规则案例测试
- 提升字段与 chains 的 discarded reason 解释质量

## 结论

当前 resolver 已经完成了“把 resolver 放进 workflow”这件事，但还没有完成“让 resolver 真正会裁决字段和后续链条”这件事。

升级版的核心不是改 schema，而是把当前的 `_materialize_resolution(window)` 替换为：

- `ResolverAgent.resolve(window)` 作为主路径
- `_materialize_resolution(window)` 作为 fallback

同时把 `triggered_chains` 的最终生成责任从 executor 迁移到 resolver。

这样我们可以在不推翻现有工作流的前提下，把 resolver 从“字段覆盖器”升级成真正的“同窗口裁决器”。
