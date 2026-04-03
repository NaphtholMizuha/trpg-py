## 上下文

当前 `dsl_node` 的主要问题已经不再是“完全不知道项目 DSL 是什么”，而是更细的一级：它常常能选对 `type.kind`，但仍然会为这些 primitive 脑补运行时不支持的参数形状。与此同时，`lint` 只能告诉它“这里错了”，却还不能可靠告诉它“这一类 step 的正确模板到底长什么样”。

以 `check.save` 为例，当前 lint 可以返回“必须定义 `dice`”，但这对模型仍然不够，因为它还不知道同一类 step 里：
- `ability` 才是正确字段，而不是 `save_ability`
- `dc` / `dc_path` 如何选择
- 还允许和不允许哪些其他字段

因此，这次变更的重点不是再扩大 DSL 词表，而是把 lint 升级成“模板指导型诊断器”，并让 `dsl_node` 显式消费这种 richer diagnostics。

## 目标 / 非目标

**目标：**
- 为受支持的 `type.kind` 建立统一的 canonical shape catalog。
- 让 `lint` 在 issue 中返回模板化诊断信息，而不仅是错误消息。
- 让 `dsl_node` prompt 明确把这些模板化诊断作为修正依据。
- 让 `dsl_node` 的目标从“尽量生成合理 DSL”收紧为“最终返回 lint valid 的结果”。
- 让测试覆盖模板化诊断契约和 `dsl_node` 对该契约的消费方式。

**非目标：**
- 不在这次变更里新增 engine primitive。
- 不要求一口气解决所有复杂 lowering 语义。
- 不要求 `lint` 变成自动修复器；它提供的是 richer guidance，不是代替模型直接改文档。
- 不强制恢复复杂的默认 repair loop；`dsl_node` 仍然可以保持较轻的控制流。

## 决策

### 决策 1：引入统一的 step shape catalog，而不是把模板散落在 lint 和 prompt 文本里

- 选择原因：如果“合法模板”只写在 prompt 文本或 lint 代码里，后续一定会再次漂移。统一 catalog 才能成为 lint、prompt、测试共享的单一真相。
- 方案：为每个受支持的 `type.kind` 定义：
  - canonical template
  - required fields
  - allowed fields
  - optional field groups
  - 常见禁止形状或常见错误键
- 替代方案：继续手工在 prompt 里补 few-shot，在 lint 里临时拼字符串。
- 未选择原因：无法形成程序可消费的稳定契约。

### 决策 2：lint issue 必须返回模板化诊断，而不是只有 message

- 选择原因：模型收到“少了 dice”仍然不知道完整期望形状；必须给它最小合法模板和 canonical example。
- 方案：`issues[*]` 至少新增一类 `expected` 信息，内容可包括：
  - `step_type`
  - `step_kind`
  - `required_args`
  - `allowed_args`
  - `example_args`
  - `notes` 或 `common_mistakes`
- 替代方案：只保留一条自然语言错误消息。
- 未选择原因：这对 `dsl_node` 来说信息量不够，无法稳定修正。

### 决策 3：dsl_node prompt 必须把“最终目标是 lint valid”写成默认约束

- 选择原因：当前 prompt 虽然讲了 DSL 词表，但没有把“最终答案必须满足 lint”写成足够硬的目标，模型容易停在“看起来像对”的半成品。
- 方案：在 system/user prompt 中明确：
  - 最终目标是返回当前 `lint` 视角下的 valid `TaskDocument`
  - 如果调用了 `lint` 且结果是 invalid，不要把该候选当作最终答案
  - 当 issue 提供模板化诊断时，优先按模板修正对应 primitive
- 替代方案：只在 lint 侧增强，不改 prompt。
- 未选择原因：模型不会自然知道要如何使用新增的 richer issue 字段。

### 决策 4：第一版模板化诊断优先覆盖高频 primitive

- 选择原因：最影响 smoke 的不是所有 primitive，而是少数高频 primitive 的参数形状反复出错。
- 方案：第一版优先覆盖：
  - `select.area`
  - `check.save`
  - `check.attack`
  - `damage.apply`
  - `resource.consume`
  - `state.set`
  - `state.adjust`
- 替代方案：一开始就覆盖所有 corner case。
- 未选择原因：范围过大，且收益不如先覆盖高频路径。

## 风险 / 权衡

- [风险] richer lint issue 会让响应变长
  - 缓解措施：模板信息只在相关 primitive 出错时返回，优先给最小合法模板和 canonical example。

- [风险] shape catalog 会成为额外维护成本
  - 缓解措施：让 lint、prompt 和测试共同复用它，确保它有明确价值回报。

- [风险] `dsl_node` 仍可能不完全遵守模板
  - 缓解措施：先把 prompt 明确成“最终必须 lint valid”，再通过 smoke 观察是否还需要更强控制流。

## Migration Plan

1. 建立统一的 step shape catalog。
2. 让 `lint` issue 生成阶段消费该 catalog，返回模板化诊断。
3. 更新 `dsl_node` prompts，要求消费 richer diagnostics 并以 `lint valid` 为最终目标。
4. 更新 `dsl_node` 节点与 smoke 输出，确保 richer issues 可见。
5. 补 lint / workflow / smoke 测试。

## Open Questions

- 模板化诊断字段命名应该更偏通用（如 `expected`），还是更偏 DSL（如 `expected_step_shape`）？
  - 更偏通用
- `example_args` 是否应当总是最小模板，还是应当尽量展示 canonical full example？
  - 展示canonical full example
- 后续是否要让 runtime 也能引用同一份 catalog，进一步减少 lint/runtime 分裂？
