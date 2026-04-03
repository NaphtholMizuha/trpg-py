## 上下文

当前 `dsl_node` 需要在一次模型上下文里同时记住：
- 受支持的 step `type.kind` 词表
- 每类 primitive 的 canonical args 模板
- 常见禁止形状与直接路径约束
- `lint` 返回的 expected template 与 common mistakes

这导致两类问题同时放大：
- prompt 越写越长，真正与当前任务相关的语义上下文被大量 DSL 教程挤占
- 即便已有 shape catalog，模型仍然常常不知道“这次任务到底该套哪一个合法模板”，从而发明字段名、错误路径前缀或非法 dice 形状

当前更像缺少一个按需取用的“模板检索层”，而不是单纯缺少更多 prompt 文案。

## 目标 / 非目标

**目标：**
- 为 `dsl_node` 提供一个 `template` 工具，使其按需获取少量高频任务族的合法 DSL 骨架。
- 让 `template` 工具输入保持收敛，优先复用 `task_node` prompt 中已有的任务原型，并通过少量枚举字段补充分支差异。
- 让 `dsl_node` prompt 从“大段内联教程”切换为“识别任务族、调用 template、填充绑定、再 lint”。
- 在第一阶段只覆盖少量高频任务，先改善稳定性与合法率，而不是一次解决全部 DSL lowering 场景。

**非目标：**
- 不把 `dsl_node` 改成纯确定性编译器。
- 不在本次引入自由文本模板签名或开放式模板搜索。
- 不要求 `template` 工具直接返回最终完整 `TaskDocument` 实例。
- 不要求第一版覆盖查询、位移、持续状态、复杂条件流或多阶段复合动作。

## 决策

### 决策 1：引入独立的 `template` 工具，而不是继续扩写 `dsl_node` prompt

- 选择原因：合法 DSL 教程本质上是可结构化知识，适合按需查询，而不是每轮都整包塞进 prompt。
- 方案：新增 `template` 工具，由 `dsl_node` 在确定任务族后调用。工具返回：
  - `template_id`
  - `description`
  - `step_order`
  - `dsl_skeleton`
  - `required_bindings`
  - `binding_rules`
  - `common_mistakes`
- 替代方案：继续在 system/user prompt 中扩充所有 primitive 模板。
- 未选择原因：会继续放大上下文占用和模板检索不稳定问题。

### 决策 2：工具输入采用“一级任务族 + 少量枚举字段”，禁止自由签名

- 选择原因：如果允许模型自由生成二级签名字符串，很快就会出现未定义签名和同义漂移。
- 方案：输入字段使用小范围枚举，例如：
  - `task_family`
  - `resolution_mode`
  - `success_rule`
  - `resource_mode`
  - `targeting_mode`
- 这些字段的可选值必须受控；未知或无法细分时允许 `unknown` 或默认回退。
- 替代方案：让模型构造自由文本 `template_signature`。
- 未选择原因：会把模板查找变成另一种 prompt 猜谜。

### 决策 3：一级任务族直接复用 `task_node` prompt 中的任务原型

- 选择原因：上游已经在使用 `single-target attack`、`single-target spell`、`area spell or area effect` 等分类；复用这套语言可以减少阶段漂移。
- 方案：`template` 工具的顶层分类直接从现有 `task_node` 原型映射而来，再用少量枚举字段补足模板分支。
- 替代方案：为 `template` 工具单独发明另一套任务类型体系。
- 未选择原因：会让上游分类和下游模板检索再次脱节。

### 决策 4：第一版只覆盖四类高频任务

- 选择原因：当前日志里最集中的失败样本主要落在攻击、豁免伤害、范围法术和治疗。
- 方案：第一版只覆盖：
  - 单体武器攻击
  - 单体豁免伤害法术
  - 范围法术伤害
  - 单体治疗或治疗增益
- 替代方案：一口气覆盖全部任务类型。
- 未选择原因：模板设计、few-shot 和测试面会快速失控。

## 风险 / 权衡

- [风险] `template` 工具过细会变成另一层复杂签名系统
  - 缓解措施：只允许少量枚举字段，严格限制第一版覆盖面，并允许 `unknown` 回退。

- [风险] `dsl_node` 仍可能错误填充模板
  - 缓解措施：模板返回 `required_bindings`、`binding_rules` 和 `common_mistakes`，并保留 `lint` 作为最终守门。

- [风险] prompt、shape catalog、template tool 可能出现三套真相
  - 缓解措施：要求 prompt 只描述工具使用方式，不再维护完整模板细节；合法模板真相下沉到 `template` 数据资产。

- [权衡] 第一版只覆盖少量任务会让部分样本继续走旧路径
  - 取舍原因：先用最小覆盖证明“按需模板检索”确实能改善合法率，再逐步扩展。

## Migration Plan

1. 新增 `template` 工具与模板定义资产。
2. 在 `dsl_node` 中挂载该工具，并将其与 `lint` 一起提供给 agent。
3. 收紧 `dsl_node` prompt，使其先识别任务族，再调用 `template`，最后填充实例参数与执行 `lint`。
4. 补充自动测试与 smoke，验证工具调用、模板回退和少量高频任务的合法 DSL 生成。
5. 基于新日志评估是否继续扩展任务族覆盖范围。

## Open Questions

- 模板资产更适合直接复用现有 `dsl_shape_catalog`，还是单独维护更高层的任务族模板表？
- 当任务族能识别但二级枚举缺失时，`template` 工具应返回最通用模板，还是显式提示调用方回退到旧策略？
- 第一版的“单体治疗或治疗增益”是否应先只覆盖 `heal.apply + resource.consume`，把纯 buff 留到后续扩展？
