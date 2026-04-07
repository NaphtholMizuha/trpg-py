## 1. 模板资产与工具定义

- [x] 1.1 新增 `template` 工具的数据模型与返回结构，至少包含 `template_id`、`step_order`、`dsl_skeleton`、`required_bindings`、`binding_rules` 和 `common_mistakes`
- [x] 1.2 定义第一版受控输入枚举字段，并实现 `unknown` 或等价保守值的回退逻辑
- [x] 1.3 为四类高频任务提供模板资产：单体武器攻击、单体豁免伤害法术、范围法术伤害、单体治疗或治疗增益

## 2. Dsl Node 集成

- [x] 2.1 在 `dsl_node` 默认工具集合中接入 `template` 工具，并保留 `lint` 工具
- [x] 2.2 调整 `dsl_node` 运行逻辑，使其优先基于任务族调用 `template` 获取合法骨架，再填充实例参数
- [x] 2.3 确保 `dsl_node` 在模板未完全命中时能够使用保守输入回退，而不是自由发明模板签名

## 3. Prompt 与验证

- [x] 3.1 更新 `planner_dsl_node_system.txt`，要求模型优先通过 `template` 工具获取合法 DSL 骨架
- [x] 3.2 更新 `planner_dsl_node_user.txt`，要求模型使用受控枚举字段调用 `template`，并根据 `required_bindings` 与 `binding_rules` 填充模板
- [x] 3.3 增加自动测试，验证 `dsl_node` 默认工具集中包含 `template`，且 prompt 不再依赖完整内联模板手册
- [x] 3.4 增加 smoke 或 workflow 验证，覆盖至少一个范围法术样本和一个单体攻击样本通过 `template` 工具生成合法 DSL
