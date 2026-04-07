## 为什么

`src/smoke/test_dsl.py` 现在只能证明 `TaskDraft -> TaskDocument -> lint` 这一段是否看起来合理，但还不能证明生成出的 DSL 真的能被 engine 执行，也不能证明它会通过 store 产生预期状态变化。随着 `dsl_node` 开始带有 repair 回路，仅看 `lint` 已经不足以判断 smoke 的最终价值。

现在是把 `test_dsl` 往后接上 engine 和 store 的合适时机：这样开发者在同一个入口里就能看到“生成是否通过 lint”、“任务是否真的可执行”以及“执行后状态是否真的发生变化”。

## 变更内容

- 扩展 `src/smoke/test_dsl.py`，让它在生成并 lint `TaskDocument` 之后，能够继续把文档交给真实 engine 执行。
- 让该 smoke 入口读取默认 world state fixture，并在执行前后对 store/state 做快照比较，输出关键状态变化摘要。
- 规定当 `lint_result` 非 `valid` 时，脚本禁止继续进入执行阶段，避免把无效 DSL 的失败与 engine 行为混在一起。
- 增加最小自动测试和一次真实样例验证，确保 `dsl smoke` 的执行阶段可观察、可回归。

## 功能 (Capabilities)

### 新增功能
- `dsl-execution-smoke`: 为 `dsl_node` smoke 增加真实 engine + store 执行验证，证明生成的 DSL 不只是“能 lint”，而且“能运行”。

### 修改功能
- `smoke-test-layout`: `test_dsl` 的输出契约将从“展示 DSL 与 lint 结果”扩展为“在 lint 通过时继续展示执行结果与关键状态变化”。

## 影响

- `src/smoke/test_dsl.py`
- 可能复用 `src/smoke/test_engine.py` 中的默认 state / roller 构造方式
- `src/tests/test_smoke_scripts.py`
- 可能新增针对 `dsl smoke` 执行阶段的最小辅助函数或共享 fixture
