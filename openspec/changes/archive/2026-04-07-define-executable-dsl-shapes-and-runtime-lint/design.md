## 上下文

这几轮 smoke 已经说明问题不再是“`dsl_node` 完全不知道 engine DSL 是什么”，而是更细的一层：
- `dsl_node` 常常能选对 primitive，但仍会发明 runtime 不接受的参数形状
- `lint` 能拦住一部分错误，但还会放过某些会在 engine 第一步就炸掉的 shape
- prompt 当前主要提供词表、few-shot 和一些 translation rules，却没有一份系统化的“合法 DSL 模板总表”

以 `select.area` 为例，模型已经知道该用 `select.area`，但仍可能输出：
- `shape: {"type": "sphere", "radius": 20}`

而 runtime 实际需要的是：
- `shape: "sphere"`
- `radius: 20`

这类问题本质上不是“缺少规则词”，而是缺少一份统一的 executable DSL shape contract。

## 目标 / 非目标

**目标：**
- 让 `lint` 尽量覆盖所有已知的 runtime-sensitive DSL 形状错误，而不是只覆盖当前 smoke 暴露的单一错误。
- 为每个受支持的 `type.kind` 提供统一的合法 shape 定义。
- 让 `dsl_node` prompt 直接消费这份合法 shape 定义，理解每类合法 DSL 的典型模板与禁止形状。
- 让 shape 定义成为 `lint`、prompt、测试和后续 smoke 的共享契约来源。

**非目标：**
- 不在这次变更里发明新的 engine primitive。
- 不要求一口气解决所有任务语义 lowering 问题。
- 不把 shape catalog 做成新的外部 DSL 文件格式，如果代码内结构更稳就优先用代码。
- 不要求 runtime 校验和 lint 逻辑完全去重；第一版允许存在“共享定义 + 分层使用”。

## 决策

### 决策 1：引入统一的 DSL shape catalog，而不是继续把模板散落在 prompt 文本中

- 选择原因：如果合法形状只存在于 prompt 里，`lint`、runtime 和测试就无法稳定复用，最终仍会出现“prompt 这么说、lint 那么查、runtime 另一套”的分裂。
- 方案：增加一个统一的 shape catalog，至少覆盖：
  - 支持的 `type.kind`
  - 必填字段
  - 允许字段
  - 明确禁止的形状
  - path/ref/when 等关键值的约束
- 替代方案：继续仅靠 prompt 手写模板和 few-shot。
- 未选择原因：这无法成为程序可消费的契约，也难以系统化扩展。

### 决策 2：lint 必须显式校验 runtime-sensitive 形状错误

- 选择原因：`lint valid` 之后再在 engine 第一步失败，会让 `lint` 失去“执行前守门员”的意义。
- 方案：把 shape catalog 中的关键 runtime-sensitive 约束前移到 `lint`，例如：
  - `select.area.shape` 必须是字符串而不是对象
  - `radius` / `origin` 等字段必须位于正确层级
  - `targets` / `target_id` / `dc` / `dc_path` 等字段形状必须与 runtime 预期一致
  - `damage` / `healing` 组件对象必须使用当前 runtime 支持的键
- 替代方案：依旧只在 runtime 阶段暴露这些错误。
- 未选择原因：会降低 smoke 和 repair loop 的反馈质量。

### 决策 3：dsl_node prompt 应由 shape catalog 派生或显式嵌入，而不是手工维护另一份独立模板

- 选择原因：如果 prompt 继续手工写另一套模板，后续 shape 演进时很容易再次漂移。
- 方案：让 `dsl_node` 的 system/user prompt 至少部分由 shape catalog 渲染，或显式引用同一份目录内容。
- 替代方案：保留现有 prompt 手工文案，只在文案里继续补例子。
- 未选择原因：长期维护成本高，而且无法保证 prompt 与 lint/runtime 同步。

### 决策 4：shape catalog 要覆盖“合法长什么样”，也要覆盖“禁止长什么样”

- 选择原因：对模型来说，仅给正例通常不够；很多 runtime 错误来自“看起来合理但实际上不支持”的嵌套写法。
- 方案：每类 shape 至少包含：
  - canonical template
  - 常见禁止形状
  - 简短解释为什么该形状不合法
- 替代方案：只给 canonical template。
- 未选择原因：这不足以约束模型远离常见脑补结构。

## 风险 / 权衡

- [风险] shape catalog 会变成另一层需要维护的元数据
  - 缓解措施：让 prompt 和 lint 直接复用它，确保这份元数据有明确回报。

- [风险] lint 约束增强后，现有一些“勉强可用”的样例会开始被判 invalid
  - 缓解措施：把这视为契约收紧的正向信号，并补对应测试与迁移说明。

- [风险] shape catalog 仍然无法覆盖所有 lowering 语义
  - 缓解措施：明确它解决的是“合法形状”和“执行前校验”，不承诺替代任务理解。

## Migration Plan

1. 定义统一的 DSL shape catalog。
2. 让 `lint` 使用这份 catalog 校验关键 runtime-sensitive 约束。
3. 更新 `dsl_node` prompt，使其显式消费或渲染该 catalog。
4. 补测试：
  - lint 能抓住新增的 runtime-sensitive 错误
  - prompt 中包含 canonical shape 约束
  - catalog 与受支持的 `type.kind` 集合保持同步

## Open Questions

- shape catalog 更适合放在 Python 模块里，还是放在配置文件/JSON 资产里？
- 是否要让 runtime 自身也显式引用这份 catalog，进一步减少重复校验？
- `when` 表达式是否也应该纳入同一份 catalog，作为独立小语法统一定义？
