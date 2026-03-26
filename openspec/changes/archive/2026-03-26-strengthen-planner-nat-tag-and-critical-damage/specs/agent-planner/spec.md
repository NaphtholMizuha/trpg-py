## 新增需求

### 需求:planner prompt 必须显式保留 DnD5e 攻击中的 nat 标签语义
系统必须让 planner 默认 prompt 在 DnD5e 攻击规划语境下显式指导模型为 `check.attack` 保留 `tags=["nat"]` 或等价的天然骰追踪语义。系统禁止继续让模型仅生成“可命中判定”的最小攻击检定步骤，却遗漏天然 20 / 天然 1 对攻击结果的规则语义。

#### 场景:planner 规划一次 DnD5e 武器攻击
- **当** planner 需要把一次近战或远程武器攻击规划为 `check.attack`
- **那么** prompt 必须明确提示攻击检定默认保留 `nat` 标签语义
- **那么** prompt 中的攻击模式或 canonical example 必须出现带 `tags=["nat"]` 的 `check.attack`
- **那么** 模型不会把天然 20 退化为普通 `success`

### 需求:planner prompt 必须显式传播攻击暴击到 damage.apply
系统必须让 planner 默认 prompt 在攻击后续包含 `damage.apply` 时，显式指导模型把前序攻击步骤的 `crit_success` 结果传播为伤害步骤的 `is_critical` 输入。系统禁止继续让 prompt 只要求“命中后造成伤害”，却遗漏暴击扩骰所需的显式链路。

#### 场景:planner 规划一次攻击命中后的伤害步骤
- **当** planner 为一次 `check.attack` 生成后续 `damage.apply`
- **那么** prompt 必须明确提示该伤害步骤在命中时执行，并在暴击时设置 `is_critical`
- **那么** prompt 中的示例必须展示从 `result.<attack-step>.outcome == crit_success` 到 `is_critical` 的映射
- **那么** 模型可以生成保留 DnD5e 暴击扩骰语义的伤害步骤

## 修改需求

## 移除需求
