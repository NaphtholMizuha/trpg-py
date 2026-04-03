## 1. DSL Shape Catalog

- [ ] 1.1 增加统一的 DSL shape catalog，覆盖当前受支持的 `type.kind` 及其 canonical 参数模板。
- [ ] 1.2 在 shape catalog 中补充常见禁止形状和关键值约束，例如 `shape`、`targets`、`damage` 组件、`path/ref/when` 形状。
- [ ] 1.3 增加测试，验证 shape catalog 与当前受支持的 `type.kind` 集合同步。

## 2. Runtime-Aligned Lint

- [ ] 2.1 扩展 `lint`，让它显式校验 runtime-sensitive DSL 形状错误，而不仅仅是当前已知单点错误。
- [ ] 2.2 让 `lint` 对新增的 shape 错误返回稳定的路径、消息和多错误聚合结果。
- [ ] 2.3 补充 `lint` 自动测试，覆盖 `select.area`、`damage.apply`、`check.save`、`path/ref/when` 等常见 shape 错误。

## 3. Prompt Alignment

- [ ] 3.1 更新 `dsl_node` prompt，使其显式消费或渲染 shape catalog，而不是只维护零散 few-shot。
- [ ] 3.2 在 prompt 中为高频 primitive 增加 canonical 模板和禁止形状说明。
- [ ] 3.3 增加 prompt / workflow 测试，验证 `dsl_node` 默认 prompt 已包含 shape catalog 的关键约束。
