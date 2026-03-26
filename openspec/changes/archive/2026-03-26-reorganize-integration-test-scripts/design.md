## 上下文

当前仓库根目录混放了几类不同职责的文件：
- 包内真正的 Python API 在 `trpg_py/`
- 单元测试在 `tests/`
- 若干手动运行的脚本仍散落在根目录，例如 `main.py`、`test_fetch_keys.py`、`test_search.py`

随着 planner 加入，根目录脚本继续增长会带来两个问题。第一，开发者不容易判断哪些文件是正式入口，哪些只是手动 smoke/integration 验证。第二，若继续把新脚本命名为 `test_*.py` 但放在 `tests/` 下，会和自动测试发现机制相互干扰。

这次设计的关键不是新增某个复杂运行时能力，而是为“手动可执行的集成验证脚本”建立稳定布局，并把 engine/search/fetch_keys/planner 四条链路的入口统一到同一目录语义下。

## 目标 / 非目标

**目标：**
- 将手动运行的集成验证脚本统一收拢到一个明确目录中。
- 将当前 demo 入口 `main.py` 重命名为 `test_engine.py`，并迁入该目录。
- 将根目录现有 `test_*.py` 脚本迁入该目录，避免继续散落在仓库根。
- 为 planner 增加可直接运行的集成测试脚本，便于观察 `ready/needs_human/blocked` 等效果。
- 更新相关规范、文档与调用示例，使新的入口布局清晰一致。

**非目标：**
- 不重做 `trpg_py` 包内 API 结构。
- 不把这些手动脚本强行接入 `unittest` 自动发现链路。
- 不要求 planner 集成脚本在本次就变成完整 benchmark 或评测框架。
- 不改变 engine/search/fetch_keys/planner 的核心业务语义，只调整手动入口和可运行验证方式。

## 决策

### 决策: 手动 smoke 脚本统一放入 `smoke/`

新目录选为仓库根下的 `smoke/`。该目录专门承载“开发者手动运行的集成验证脚本”，与 `tests/` 中被自动发现的单元/集成测试分开。

考虑过的替代方案：
- 放入 `tests/`：文件名本身以 `test_` 开头，容易被 `unittest discover` 误收。
- 继续留在根目录：目录语义模糊，且会继续累积杂项入口。
- 放入 `scripts/`：能解决根目录拥挤，但无法从命名上表达“这是测试/验证入口”。

### 决策: demo 入口直接改名为 `smoke/test_engine.py`

这次不保留 `main.py` 作为长期主入口，而是将其明确重命名为 `test_engine.py` 并移动到 `smoke/`。这样能把它的角色清楚标成“手动验证 engine 效果的脚本”，与包内正式 API 区分开。

考虑过的替代方案：
- 保留 `main.py` 并额外复制一份 `test_engine.py`：会制造双入口和文档分叉。
- 只移动不改名：路径改善了，但脚本职责依然不够直观。

### 决策: 现有根目录 `test_*.py` 手动脚本整体迁入同一目录

`test_fetch_keys.py`、`test_search.py` 以及新增的 planner 脚本都放入 `smoke/`，保持统一的“手动验证入口”心智模型。已有单元测试文件仍继续保留在 `tests/`。

考虑过的替代方案：
- 只迁一部分脚本：会让目录规则再次变得模糊。
- 将 search 脚本排除在外：不符合“根目录以 test 开头的文件统一收拢”的目标。

### 决策: planner 集成脚本聚焦“观察效果”，不是替代测试框架

新增的 planner 脚本命名为 `smoke/test_planner.py`。它的目标是让开发者手动输入或选择 DM 指令、加载示例 state，并直接观察 planner 的结构化输出状态。脚本至少要能展示 `ready/needs_human/blocked` 三类结果中的若干代表场景，并在依赖不可用时清楚暴露阻塞原因。

考虑过的替代方案：
- 直接做 benchmark/eval 框架：目标过大，不适合作为当前变更的第一步。
- 只保留单元测试，不提供手动脚本：不满足“我要测试 planner 效果”的需求。

## 风险 / 权衡

- [脚本迁移后旧命令失效] → 在规范和 README 中明确新命令，并把这次 change 标记为 breaking。
- [`smoke/` 与 `tests/` 的边界被后续混用] → 通过新增布局规范明确“手动可执行脚本”与“自动发现测试”的职责差异。
- [planner 集成脚本依赖真实模型或外部服务，导致体验不稳定] → 允许脚本清晰输出 `blocked`，并要求支持显式传参与示例场景。
- [engine 脚本改名影响现有文档和习惯] → 在任务中显式加入命令、README、测试同步项，避免只改文件不改说明。

## Migration Plan

1. 新增 `smoke-test-layout` 规范，定义 `smoke/` 目录职责和根目录脚本收敛规则。
2. 修改 `demo-runner` 规范，把 `main.py` 入口切换为 `smoke/test_engine.py`。
3. 修改 `fetch-keys-tool` 与 `agent-search-tool` 规范，把现有手动脚本迁入集成测试目录。
4. 修改 `agent-planner` 规范，新增 `smoke/test_planner.py` 的可运行要求。
5. 实现时迁移脚本、更新 README/测试，并确保自动测试发现不把这些脚本误当作 `tests/` 套件的一部分。

回滚策略：若目录调整造成过大干扰，可暂时恢复旧脚本路径并在新路径保留兼容包装，但长期目标仍是只保留集成测试目录中的单一入口。

## Open Questions

- planner 集成脚本是否需要内置多个固定场景（例如 `ready` / `needs_human`），还是先支持单场景 + CLI 输入即可？
- `smoke/` 中是否还需要 README 或索引文件，统一列出 engine/search/fetch_keys/planner 的手动命令？
