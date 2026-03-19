# Resolver Window 设计文档

## 目标

引入一个 `resolver` 阶段，在任何 world-state 真正写入之前，先对同一个结算窗口中的多个 `Executor` 结果进行合并。

这个设计主要用于解决以下问题：

- 法术 -> 反应施法 -> 法术反制
- 攻击 -> 防御性反应
- 直接状态变化 -> 同窗口内被后续结果覆盖

`resolver` 的职责是为当前结算窗口产出最终生效的 `field_changes`，而不是替 DM 自动推进后续世界演化。

## 为什么需要 Resolver

当前系统存在几个问题：

- `executor` 擅长产出单步动作的直接结果，但不擅长合并同一窗口内彼此竞争的多个结果。
- `commiter` 应该只负责写入最终确认的变更，而不应该负责判断哪些冲突变更应该生效。
- 有些反应本来就属于同一个规则结算窗口，应该自动合并，而不是交给 DM 手工拼接。

典型例子：

- `魔法飞弹` 和 `护盾术` 属于同一个结算窗口。
- `护盾术` 和 `法术反制` 也属于同一个结算窗口。
- “卸下护甲”和“AC变化”存在关联，但 AC 重算究竟是同窗口自动结算，还是作为后续建议交给 DM，可以留待更细的规则策略决定。

## 职责边界

`resolver` 负责：

- 读取同一个结算窗口中的多个 executor 结果
- 理解这些结果的记录顺序与结算优先级
- 判断哪些 `field_changes` 最终仍然有效
- 产出一份可提交给 `commiter` 的最终合并结果

`resolver` 不负责：

- 产生新的随机掷骰
- 直接写入 world state
- 自动推进未来场景
- 替代 DM 对“窗口外后续发展”的判断

## 高层流程

推荐流程：

1. `planner`
2. `executor`
3. `executor` 输出后，系统询问 DM：是否存在优先级更高、且仍属于同一结算窗口的动作
4. 如果 DM 确认存在，则重入 `planner -> executor`
5. 重复以上过程，直到 DM 不再追加更高优先级动作
6. `resolver`
7. `commiter`

也就是说，`resolver` 接收的是一个逻辑上属于同一结算窗口的多次 executor 结果，对其进行合并，然后只把最终结果交给 `commiter`。

## DM 追加高优先级动作

这个机制的核心是：

- `executor` 输出后并不立刻提交
- 系统要先询问 DM：是否存在一个优先级更高、并且仍属于当前结算窗口的动作

如果答案是“有”，则：

- 当前结果先暂存在 window 中
- 不进入 `commiter`
- 使用新的 DM 指令重入 `planner`
- 新的任务再交给 `executor`
- 新的 executor 结果继续追加到当前 window

如果答案是“没有”，则：

- 当前 window 关闭
- 交给 `resolver` 统一合并
- 再由 `commiter` 写入最终结果

这个机制适合处理：

- 护盾术
- 法术反制
- 反制反制
- 同窗口内的即时响应动作

它的意义在于：

- 不要求 planner 一次性预知整条响应链
- 不要求 executor 单次结算就穷尽所有后续
- 允许 DM 按跑团实际节奏逐步补入高优先级动作

## Window 的形成方式

一个 `ResolutionWindow` 不是一次 `executor` 调用的结果，而是：

- 一次主动作的执行结果
- 加上若干次由 DM 追加的、仍属于同一结算窗口的高优先级动作结果

因此，window 本质上是一个“待提交前的结算缓存”。

只有当 DM 不再追加更高优先级动作时，这个 window 才进入 resolver。

在当前 V1 设计中，workflow 直接维护：

```python
active_window: ResolutionWindow | None
```

也就是说，`ResolutionWindow` 同时承担：

- 运行时中的结算窗口收集容器
- 传给 resolver 的输入对象

这样做是为了先降低实现复杂度；如果后续 `window_review` 需要明显更多的流程态字段，再考虑拆出独立的运行时结构。

## 核心概念：Resolution Window

`ResolutionWindow` 是一个结构化容器，用来打包所有属于同一即时结算上下文的 executor 运行结果。

例如：

- 一个法术及其响应法术
- 一次攻击及其立即发生的防御性反应
- 一个触发动作及其同窗口内的打断效果

这个 window 主要是为 LLM resolver 设计的可读 schema，而不是一个完全硬编码的规则引擎。

## Window Schema

当前设计刻意保持简洁。

每个 run 只有两个关键顺序字段：

- `order`: 记录顺序，表示该结果何时进入 window
- `priority`: 结算优先级，表示 resolver 合并时应优先考虑谁

这样设计的原因是：

- 记录顺序 和 规则结算顺序 往往不是一回事

例如：

- `魔法飞弹` 可能先出现，因此 `order` 更小
- `护盾术` 后宣告，因此 `order` 更大
- 但在规则结算上，`护盾术` 的效果会更早影响结果，因此它应有更小的 `priority`

### 建议输入 Schema

```json
{
  "window_id": "window_001",
  "root_task_id": "task_magic_missile_001",
  "root_description": "马利克对艾尔德拉施放魔法飞弹",
  "status": "open",
  "shared_context": [
    "[KV Malik.combat] HP: 32/32 | 反应: 可用",
    "[KV Aldera.combat] HP: 44/44 | AC: 18 | 反应: 可用",
    "[RAG 魔法飞弹] 自动命中，造成 3d4+3 力场伤害",
    "[RAG 护盾术] 被魔法飞弹指定时可施放，使其伤害无效",
    "[RAG 法术反制] 可对正在施放的法术进行反制"
  ],
  "runs": [
    {
      "order": 0,
      "priority": 10,
      "task_id": "task_magic_missile_001",
      "description": "马利克对艾尔德拉施放魔法飞弹",
      "actor": "Malik",
      "target": "Aldera",
      "success": true,
      "narration": "魔法飞弹将造成 11 点力场伤害。",
      "field_changes": [
        {
          "path": "Aldera.combat.HP",
          "old_value": "44/44",
          "new_value": "33/44",
          "operation": "MOD",
          "source": "task_magic_missile_001"
        }
      ],
      "triggered_chains": []
    },
    {
      "order": 1,
      "priority": 5,
      "task_id": "task_shield_001",
      "description": "艾尔德拉施放护盾术",
      "actor": "Aldera",
      "target": "Aldera",
      "success": true,
      "narration": "护盾术使魔法飞弹伤害无效。",
      "field_changes": [
        {
          "path": "Aldera.spell_slots.1环",
          "old_value": "4/4",
          "new_value": "3/4",
          "operation": "MOD",
          "source": "task_shield_001"
        }
      ],
      "triggered_chains": []
    }
  ]
}
```

### 当前落地的类型约束

为减少后续接入成本，项目内的 schema 与现有 `ExecutionResult` / `StateChange` 做了直接对齐：

- 输入类型为 `ResolutionWindow`
- 单次运行记录为 `ResolutionWindowRun`
- 输出类型为 `ResolutionResult`
- 被丢弃的变更为 `DiscardedStateChange`

额外补充的契约字段：

- `status`: 标记 window 当前处于 `open` / `ready` / `resolved`
- `success`: 保留 executor 原始执行状态，供 resolver 判断这次 run 是否只是打开了反应窗口
- `triggered_chains`: 暂不由 resolver 自动推进，但保留在 run 中，避免 executor 信息丢失

## Resolver 输出 Schema

`resolver` 应该输出一份紧凑的合并结果。

### 建议输出 Schema

```json
{
  "window_id": "window_001",
  "final_field_changes": [
    {
      "path": "Aldera.combat.HP",
      "old_value": "44/44",
      "new_value": "33/44",
      "operation": "MOD",
      "source": "resolver:window_001"
    }
  ],
  "discarded_field_changes": [
    {
      "path": "Aldera.spell_slots.1环",
      "old_value": "4/4",
      "new_value": "3/4",
      "operation": "MOD",
      "source": "task_shield_001",
      "discarded_by": "resolver:window_001",
      "reason": "如果护盾术被后续结果判定为无效，则其消耗不生效"
    }
  ],
  "resolution_summary": "resolver 对同一结算窗口内的多次执行结果完成合并，保留最终有效的状态变更。",
  "dm_suggestions": [
    "若本窗口结算后引发新的独立规则问题，请由 DM 决定是否开启下一窗口。"
  ]
}
```

## `order` 与 `priority` 的含义

`order`

- 表示记录顺序
- 数值越小，表示越早进入当前 window

`priority`

- 表示结算优先级
- 数值越小，表示 resolver 合并时越早处理

在收集阶段，如果 DM 追加了同窗口动作但没有显式填写 `priority`，默认规则为：

- 取当前 `active_window.runs` 中最小的 `priority`
- 新 run 的 `priority = min(existing_priorities) - 1`

这保证了新追加动作默认总是比当前窗口里已有动作优先级更高。

resolver 的排序建议为：

1. 先按 `priority`
2. 再按 `order`

这样可以表达：

- 某个反应虽然是后记录的
- 但在规则上会更早影响主动作结果

## 为什么使用 LLM Resolver，而不是硬编码规则

本项目采用的是半结构化 world state，并且 TRPG 场景天然开放。

如果把所有同窗口交互都写成硬编码，会很脆弱，因为：

- 新反应、新物品效果会不断出现
- world state 本来就是开放式的
- 很多互动是语义级的，不是单纯的数值覆盖

LLM resolver 的优势在于：

- 能把多个 executor 结果放在一起理解
- 能理解“后发生的响应如何影响先前动作的结果”
- 能在不写死具体场景的情况下保持更高的泛化能力

## 为什么不让 Resolver 自动推进世界

这里必须区分两类东西：

- 同窗口内可合并的响应链
- 窗口结束后才会展开的后续发展

resolver 应处理第一类，例如：

- `护盾术`
- `法术反制`
- 同一动作窗口内的防御或打断反应

但是 resolver 不应该自动处理第二类，例如：

- 目标倒地后 DM 是否进入昏迷/死亡流程
- NPC 在下一拍会做什么
- 是否开启一个新的场景窗口

这些更适合作为建议交给 DM，而不是由 resolver 自动执行。

## Resolver 的工具建议

resolver 不应该直接写入 world state。

建议具备的工具：

- `read`
- `search`
- `fetch_keys`

`evaluate` 可以作为可选项。

如果设计目标是“只做合并与裁决”，而不是继续随机结算，那么最好尽量减少 resolver 中的新掷骰。

## 非目标

这份设计文档暂时不定义以下内容：

- `ResolverAgent` 的具体实现方式
- reaction window 如何被打开
- 一个 window 中最多允许多少次 run
- post-window DM 建议如何在 UI 上展示

这些属于后续设计任务。

## 建议的下一步

先只实现 schema 与流程契约，不急着一次做完所有功能：

1. 在 `src/types.py` 中增加 `ResolutionWindow` 相关类型
2. 把多个 executor 结果收集到一个 window 中
3. 增加 resolver prompt，让它消费 window 并输出合并结果
4. 让 `commiter` 只写入 `final_field_changes`

这样可以在最小实现成本下，先验证这套“window 合并”方案是否适合项目。

补充阅读：

- `window` 的具体收集方式见 `docs/resolver-window-collection-design.md`
- `resolver` 从当前骨架版升级为真正裁决器的设计见 `docs/resolver-upgrade-design.md`
