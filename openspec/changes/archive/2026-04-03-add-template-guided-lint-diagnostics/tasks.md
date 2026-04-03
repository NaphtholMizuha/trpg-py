## 1. 形状目录

- [x] 1.1 新增统一的 DSL step shape catalog，优先覆盖 `select.area`、`check.save`、`check.attack`、`damage.apply`、`resource.consume`、`state.set`、`state.adjust`
- [x] 1.2 为每类高频 primitive 定义 canonical template、required fields、allowed fields 和常见错误形状

## 2. Lint 诊断升级

- [x] 2.1 扩展 `lint` issue 结构，支持返回模板化诊断字段
- [x] 2.2 让 `lint` 在高频 primitive 出错时返回 required fields、canonical example 和常见错误提示
- [x] 2.3 补充 `src/tests/test_agent_lint.py` 或等价测试，覆盖 richer issue 结构

## 3. DslNode 适配

- [x] 3.1 更新 `planner_dsl_node_system.txt`，明确最终目标是 `lint valid`
- [x] 3.2 更新 `planner_dsl_node_user.txt`，明确如何消费模板化 lint 诊断
- [x] 3.3 更新 `src/tests/test_planner_workflow.py`，覆盖 `dsl_node` 消费 richer lint issues 的场景

## 4. Smoke 验证

- [x] 4.1 更新 `src/smoke/test_dsl.py` 或相关输出，使 richer lint issues 在 smoke 中可观察
- [x] 4.2 手动运行 `uv run src/smoke/test_dsl.py`，确认 invalid 结果中能看到模板化诊断信息
