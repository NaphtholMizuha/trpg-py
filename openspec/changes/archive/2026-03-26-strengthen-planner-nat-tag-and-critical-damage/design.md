## 上下文

当前引擎已经具备正确的 DnD5e 攻击暴击语义：攻击检定在存在 `nat` 标签时会把天然 20 映射为 `crit_success`，而 `damage.apply` 在 `is_critical=true` 时会额外扩展一组伤害骰且不会重复计算固定加值。最近的 live smoke 暴露的问题不在执行层，而在 planner 产物层：模型有时会生成“结构合法、可执行，但没有完整保留暴击语义”的 TaskDocument。

当前默认 prompt 虽然在 canonical example 里展示了 `tags=["nat"]` 和 `is_critical`，但攻击规划模式本身仍偏“最小合法文档”导向，没有把这两个字段提升为 DnD5e 攻击规划中的默认约束。现有 lint 与自动测试也没有专门守住这条语义链。

## 目标 / 非目标

**目标：**
- 让 planner 默认 prompt 明确要求 DnD5e 攻击检定保留 `nat` 标签语义。
- 让 planner 默认 prompt 明确要求攻击后的 `damage.apply` 从前序 `crit_success` 映射出 `is_critical`。
- 为该语义补充回归测试和 smoke 复核任务，降低后续提示词演化时再次回退的风险。

**非目标：**
- 不修改执行器中的暴击结算规则。
- 不把所有伤害步骤都强制要求携带 `is_critical`，仅针对来源于攻击检定结果的典型链路提供明确规划约束。
- 不在本次变更中扩展新的 combat operation 类型或新的规则系统。

## 决策

### 决策 1：优先强化 planner prompt，而不是修改引擎

引擎当前语义已经符合主规格：`check.attack + nat` 产出 `crit_success`，`damage.apply + is_critical` 触发暴击扩骰。因此本次应把问题视为 planner 生成约束不足，而不是执行器规则缺陷。

考虑过的替代方案：
- 修改引擎，在天然 20 时自动把后续伤害视为暴击。
  不采用，因为这会让执行层隐式猜测 planner 意图，削弱 TaskDocument 作为执行 DSL 的显式性。
- 修改 store 或 world state，让武器配置直接编码暴击逻辑。
  不采用，因为暴击属于攻击结果语义，不应被折叠进静态武器数据。

### 决策 2：把 `nat` 与 `is_critical` 写成攻击规划模式的一部分

prompt 中已有 canonical example，但这还不足以稳定约束模型。设计上需要在“Attack planning pattern”或等价显式指导里直接说明：
- `check.attack` 默认包含 `tags=["nat"]`
- 若后续存在 `damage.apply`，其 `is_critical` 应来自 `result.<attack-step>.outcome == crit_success`

考虑过的替代方案：
- 只保留 canonical example，不新增显式规则句。
  不采用，因为模型已经证明会退化到“最小合法文档”。
- 只在 system prompt 中增加一句提醒。
  不采用，因为用户 prompt 中的结构化示例与模式指导更直接影响最终文档形状。

### 决策 3：先用 prompt 与测试守护，暂不把该语义提升为 lint 硬错误

本次优先解决 planner 缺失暴击语义的问题。lint 当前负责结构与执行器语义合法性校验，而“攻击规划是否保留了完整 DnD5e 语义”更接近规划质量约束。立即把它做成 lint 硬错误，可能会误伤某些非 DnD5e 或非攻击来源的伤害步骤。

考虑过的替代方案：
- 让 lint 在检测到 `check.attack` 后强制要求 `nat`
  不采用，因为 lint 目前不承载 ruleset-specific planning quality policy。
- 让 lint 在 `damage.apply` 缺失 `is_critical` 时直接 invalid
  不采用，因为并非所有伤害步骤都来自攻击检定，也并非所有规则集都使用同样的暴击路径。

## 风险 / 权衡

- [prompt 更长、更强约束，可能压缩其他提示空间] → 只补最关键的攻击/暴击语义，不扩展成泛化战斗教学。
- [自动测试无法证明真实 LLM 100% 总会遵守新提示] → 用 prompt 内容断言守住明示指导，并保留手动 smoke 复核任务。
- [未来若接入非 DnD5e 规则集，`nat` 指导可能过于默认化] → 将表述限定在 DnD5e 攻击规划语境，避免扩展为所有检定默认行为。
