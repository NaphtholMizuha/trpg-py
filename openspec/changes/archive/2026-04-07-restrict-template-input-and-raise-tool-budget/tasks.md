## 1. Template 输入契约

- [x] 1.1 将 `template` 工具输入字段收紧为受控枚举或等价严格校验，并同步更新模板目录查询入口
- [x] 1.2 为非法 template 枚举输入实现可观察的快速失败，区分“输入非法”和“合法但无匹配模板”
- [x] 1.3 为 `template` 的合法枚举值、`unknown` 回退和非法输入日志补充自动测试

## 2. DSL 节点预算与提示词

- [x] 2.1 提高 `dsl_node` 默认工具调用预算，并确保 recursion limit 覆盖“一次误查 + 一次回退 + 一次 lint”链路
- [x] 2.2 更新 `dsl_node` 的 system/user prompt，要求仅使用文档化 template 枚举值并把 `unknown` 作为唯一保守回退
- [x] 2.3 为默认预算和 prompt 约束补充 workflow 级自动测试，验证不再依赖自由拼写命中模板

## 3. Smoke 验证

- [x] 3.1 运行 `dsl` smoke，确认真实工具日志能区分非法 template 输入、合法回退和后续 lint 路径
