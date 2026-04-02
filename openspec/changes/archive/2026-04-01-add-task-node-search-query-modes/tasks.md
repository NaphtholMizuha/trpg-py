## 1. Search 接口与日志

- [x] 1.1 为 `src/augury/planner/tools/search.py` 的输入 schema 增加 `mode` 字段，支持 `term`、`balanced`、`semantic`
- [x] 1.2 更新 `search` 工具描述与默认行为，使其不再统一要求 HyDE 查询，而是解释三种模式的用途
- [x] 1.3 在 search 调用日志中记录 `mode`，便于观察 task_node 的检索选择

## 2. Task Node Prompt 适配

- [x] 2.1 在 `config/prompts/planner_task_node_system.txt` 中新增 query planning 规则，要求先判断是否存在明确规则术语，再选择 `term`、`balanced` 或 `semantic`
- [x] 2.2 将当前对 HyDE 查询的要求收窄为仅适用于 `semantic` 模式，并为 `term` 与 `balanced` 补充 query 构造约束
- [x] 2.3 在 system prompt 的 few-shot 中各增加一个 `term`、`balanced`、`semantic` 示例
- [x] 2.4 在 `config/prompts/planner_task_node_user.txt` 的 requirements 中加入三模式选择与 query 构造规则

## 3. 测试与验证

- [x] 3.1 更新 `src/tests/test_agent_search.py`，覆盖 `mode` 字段的输入校验、默认值和日志输出
- [x] 3.2 增加 task_node prompt / smoke 测试，验证明确术语场景优先使用 `term` 或 `balanced`
- [x] 3.3 增加 `火球术` 相关 smoke case，验证 query 不再被统一改写为宽泛 HyDE 描述
- [x] 3.4 验证无明确术语场景仍可使用 `semantic` 模式得到合理规则命中
