# Phase 1 Eval 优化方案

## 背景

这份文档基于最新一轮 Phase 1 真实评测结果整理，评测目录为：

- `evals/reports/phase1/20260321-183511/`

本轮评测对同一批 `planner / executor / resolver` case 连续运行了 5 次，目标不是观察一次性结果，而是识别：

- 稳定失败项
- 偶发失败项
- 已经基本稳定的能力

## 当前结论

最新汇总结果：

- `planner`: 10 个样本中通过 5 个，`pass_rate = 0.5`
- `executor`: 10 个样本中通过 9 个，`pass_rate = 0.9`
- `resolver`: 10 个样本中通过 7 个，`pass_rate = 0.7`

按 case 稳定性看：

- `planner_actor_target_normalization`: `5/5`
- `planner_magic_missile_basic`: `0/5`
- `executor_magic_missile_damage`: `4/5`
- `executor_narration_only_window_open`: `5/5`
- `resolver_discarded_path_present`: `2/5`
- `resolver_path_conflict_overwrite`: `5/5`

这说明当前系统的主要问题不是全面失效，而是集中在两个明确方向：

1. `planner` 对资源字段写回目标的规划不稳定，且在当前 case 中表现为稳定失败
2. `resolver` 对“被取消动作的资源消耗是否应进入 discarded”这一语义不稳定

与此同时，有两块能力已经基本站稳：

- actor / target 归一
- 基础路径冲突覆盖

## 问题分层

### 1. Planner：资源消耗字段漏规划

现象：

- `planner_magic_missile_basic` 在 5 次运行中全部失败
- 失败原因稳定一致：缺少 `Malik.spell_slots.1环`

这意味着当前 planner 对“动作直接成本”没有稳定写入 `write_targets`。

风险：

- 后续 executor 即使知道要消耗法术位，也可能缺少明确写回提示
- `write_targets` 作为收口约束时，会放大 planner 漏项问题
- 评测场景一旦增多，这类“资源成本漏写”会成为系统性短板

根因判断：

- 当前 planner 能稳定识别目标实体和结果目标，例如 `Aldera.combat.HP`
- 但对“行动者资源消耗”没有同等强度的抽取规则
- 模型更倾向把“伤害目标”当主写回对象，而把“施法成本”留在 narration / execution_steps 层

### 2. Resolver：discard 语义不稳定

现象：

- `resolver_discarded_path_present` 仅 `2/5` 通过
- 同一 case 中，resolver 有时会把 `Aldera.spell_slots.1环` 放进 `discarded`
- 有时又把同一路径保留在 `final_field_changes`

风险：

- 同窗口裁决结果不稳定，直接影响 `commiter` 真实性
- 资源消耗是否生效会随着模型波动而变化
- 这类问题比路径冲突更隐蔽，因为表面上 schema 合法，但语义不一致

根因判断：

- 当前 resolver 已经能处理“同一路径谁覆盖谁”
- 但对“动作整体失效时，其资源消耗是保留还是 discard”没有稳定内化
- `resolver_discarded_path_present` 这类 case 更像“按语义裁决 run”，而不是“按 path 覆盖”

### 3. Executor：整体趋稳，但仍有偶发波动

现象：

- `executor_magic_missile_damage` 为 `4/5`
- 大多数情况下能够同时写出：
  - `Malik.spell_slots.1环`
  - `Aldera.combat.HP`
- 但仍然有个别运行出现漏写或异常表达

风险：

- 虽然已经不是当前最紧急问题，但在 workflow 场景中仍可能造成偶发脏状态

根因判断：

- executor 当前已经基本理解“资源消耗 + 目标效果”双写回
- 但结构化输出与 narration 仍可能偶发不同步
- 这更像稳态优化问题，不是当前第一优先级

## 优化优先级

推荐优化顺序：

1. `planner`
2. `resolver`
3. `executor`

原因：

- `planner_magic_missile_basic` 是稳定失败项，说明这里存在规则层面的固定缺口
- `resolver_discarded_path_present` 是当前最主要的不稳定项，说明这里存在语义层面的摇摆
- `executor` 已接近可用，应该先避免为了修 10% 波动而打乱更核心的规划与裁决边界

## 优化目标

### Planner 优化目标

目标：

- 当任务存在显式资源消耗时，`write_targets` 必须包含对应资源路径
- 对施法、消耗法术位、使用反应等场景，行动者资源字段应优先于次要上下文字段

最低验收标准：

- `planner_magic_missile_basic` 达到 `5/5`
- 不新增无关 `write_targets`

### Resolver 优化目标

目标：

- 当动作被上位效果或后续裁决判定为无效时，相关资源消耗要么稳定保留，要么稳定 discarded
- 同一种 case 在多次运行中，`final/discarded` 分类应保持一致

最低验收标准：

- `resolver_discarded_path_present` 达到至少 `4/5`
- `resolver_path_conflict_overwrite` 继续保持 `5/5`

### Executor 优化目标

目标：

- narration 中明确声明的直接结果，必须稳定反映到结构化字段变更中
- 避免资源字段重复出现在多个 bucket 中

最低验收标准：

- `executor_magic_missile_damage` 达到 `5/5`
- `executor_narration_only_window_open` 保持 `5/5`

## 具体优化建议

## A. Planner 优化

### 建议 1：强化 `write_targets` 的规则后处理

不要完全依赖模型自行产出 `write_targets`。

建议在 planner 后处理阶段增加一层规则：

- 如果 `actor` 已知，且上下文中存在 `actor.spell_slots`
- 且 `description / execution_steps / context` 中出现施法、法术位、X环等线索
- 则自动把对应 `actor.spell_slots.<level>` 补进 `write_targets`

这层逻辑应尽量做成“补强”，而不是粗暴覆盖模型结果。

### 建议 2：区分“动作成本字段”和“效果字段”

当前 planner 更容易关注目标效果字段。

建议在 prompt 或后处理里显式要求：

- 先列动作成本字段
- 再列目标结果字段

例如统一顺序为：

1. 行动者资源消耗
2. 目标主效果
3. 条件性效果

### 建议 3：把 `write_targets` 评测约束前移到 prompt

可以在 planner prompt 中加硬约束：

- 如果动作会消耗已知资源，则必须把该资源字段写入 `write_targets`

这样做的价值是把“评测要求”转成“生成要求”。

## B. Resolver 优化

### 建议 1：把“资源消耗是否随动作失效而 discarded”写成显式裁决规则

当前 resolver 更像在自由发挥。

建议在 resolver prompt 中加入更明确的契约：

- 如果一个动作被判定为未生效，需要明确判断其资源消耗是否仍然成立
- 不允许既把该消耗保留为 final，又同时在 discarded 中重复表达同一含义

### 建议 2：先按 run 级别判断，再落到 change bucket

当前不稳定，很像是在字段级做局部裁决。

建议内部推理顺序强调：

1. 先判断该 run 是否成立 / 部分成立 / 失效
2. 再决定资源消耗、主效果、条件效果分别落在哪个 bucket

这样比直接看 path 更符合 `resolver_discarded_path_present` 的 case 语义。

### 建议 3：收紧 `discarded` 的输出一致性

对于同一路径：

- 如果进入 `discarded_*`
- 就不应同时作为最终生效结果继续保留在 `final_*`

至少在同一个 case 中，要避免这种自相矛盾的双写状态。

## C. Executor 优化

### 建议 1：补一个更强的结果一致性后处理

如果 narration 明确出现：

- “造成 X 点伤害”
- “生命值减少到 Y”
- “消耗 1 个 1 环法术位”

而 `field_changes` 未体现相应结果，则应视为结构化结果不完整。

这层既可以做 prompt 约束，也可以做 sanitize 后校验。

### 建议 2：去重 bucket 间的重复 change

当前某些运行里同一路径可能同时出现在 `resource_costs` 和 `primary_effects`。

建议在 executor 后处理时统一去重，避免重复字段干扰 resolver 和评测。

## 评测集本身也要优化

这次结果还暴露出一个事实：

- 当前 case 数量仍然偏少
- 某些 case 对语义边界的描述不够强

下一步建议：

### 1. 补充 planner 资源字段 case

例如：

- 攻击消耗弹药
- 法术反制消耗 3 环位
- 反应已消耗标记

### 2. 补充 resolver 资源消耗语义 case

把以下几种情况拆开：

- 动作效果失败，但资源消耗仍成立
- 动作整体无效，资源消耗也应 discarded
- 资源消耗与主效果分离成立

### 3. 在 summary 中增加 failure pattern 聚合

目前已有 `case_stability`，但还缺少：

- 各类 failure code 计数
- 各类 failure code 的 run 分布

这会让后续优化更快定位。

## 建议实施顺序

### Phase 1A

先修 planner：

- 为 `write_targets` 增加资源字段补强后处理
- 重新跑 5 次评测

目标：

- `planner_magic_missile_basic` 从 `0/5` 提升到 `5/5`

### Phase 1B

再修 resolver：

- 收紧 discarded 语义
- 强化 run 级裁决规则

目标：

- `resolver_discarded_path_present` 从 `2/5` 提升到 `4/5` 以上

### Phase 1C

最后修 executor：

- 去重 field_changes
- 强化 narration 与结构化输出一致性

目标：

- `executor_magic_missile_damage` 从 `4/5` 提升到 `5/5`

## 验收标准

下一轮优化完成后，建议用同样的 `testp1.py --repeats 5` 重新验收，并以以下标准判断是否通过：

- `planner` 整体 `pass_rate >= 0.9`
- `executor` 整体 `pass_rate = 1.0`
- `resolver` 整体 `pass_rate >= 0.9`
- 所有当前已有 case 的单项稳定性不得低于 `4/5`

## 结论

这轮最新评测结果说明：

- 系统已经不是“全局不稳”
- 而是进入了“局部短板非常明确”的阶段

当前最值得做的，不是大规模重构，而是针对评测暴露出来的两个关键缺口精准补强：

- planner 的资源字段规划
- resolver 的 discarded 语义

只要这两块补上，当前 Phase 1 的整体稳定性应该会有明显提升，之后再进入 workflow 端到端评测会更稳。
