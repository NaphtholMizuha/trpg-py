## 1. Internal ReAct Repair Loop

- [x] 1.1 扩展 `src/augury/planner/nodes/dsl_node.py`，让 repair 回路保持在单个 `dsl_node` 内部，而不是新增外层 LangGraph 节点或新的 planner 阶段。
- [x] 1.2 让 `dsl_node` 的 agent 以 ReAct/tool-use 形式调用 `lint`，支持“首轮生成 -> lint -> repair -> 再 lint”的有限预算回路。
- [x] 1.3 为 repair 阶段定义稳定输入，至少包含 `TaskDraft`、当前 candidate `TaskDocument` 和结构化 lint issues。
- [x] 1.4 让 `DslNode.run()` 在 repair 成功时提前停止，在预算耗尽时返回最后 candidate 和最终 lint 结果。

## 2. Prompting And Tool Budget

- [x] 2.1 为 repair 阶段增加独立 prompt 段或等价消息结构，要求模型尽量保留已合法步骤并只修复 lint 明确指出的问题。
- [x] 2.2 在提示词中明确规定 `lint` 的最小/最大调用次数、成功即停止和预算耗尽即返回最后 candidate 的规则。
- [x] 2.3 补充测试或 prompt 断言，验证 repair 阶段不会退化成完全自由重写，并且 `lint` 工具使用受预算约束。

## 3. Validation

- [x] 3.1 更新 `src/tests/test_planner_workflow.py`，覆盖 lint 非法后触发 repair、repair 通过后提前停止、预算耗尽后返回最终失败结果等路径。
- [x] 3.2 为 `dsl_node` 增加工具调用行为测试，验证 repair 回路保持在 node 内部，并验证 `lint` 调用次数符合提示词预算。
- [x] 3.3 更新 `src/tests/test_smoke_scripts.py`，让 `dsl_node` smoke 入口的最小自动测试覆盖 repair 回路的可观察输出。

## 4. Smoke

- [x] 4.1 更新 `src/smoke/test_dsl.py`，展示 repair 是否触发、轮次信息和最终 lint 结论。
- [x] 4.2 用 Fireball 样例手动运行 `src/smoke/test_dsl.py`，确认 repair 回路至少能让 candidate 朝合法 DSL 收敛，或在失败时留下更可调试的最终结果。
