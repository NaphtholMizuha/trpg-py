## 为什么

当前仓库仍采用“包目录、`smoke/`、`tests/` 平铺在仓库根目录”的布局，并且大量脚本通过把仓库根插入 `sys.path` 来导入 `trpg_py`。随着 engine、planner、RAG 和 smoke 脚本持续增加，这种布局让安装、测试发现、脚本入口和公共导入命名空间都越来越模糊，也使后续包重命名和发布流程变得脆弱。

## 变更内容

- 新增标准 `src/` 源码布局，将 Python 运行时代码迁移到 `src/augury/`，并以 `augury` 取代现有 `trpg_py` 作为唯一长期包命名空间。
- 将手动 smoke 脚本从仓库根下的 `smoke/` 迁移到 `src/smoke/`，并将自动测试从 `tests/` 迁移到 `src/tests/`，明确“运行时代码 / 手动验证 / 自动测试”三类内容在 `src/` 下的边界。
- 同步更新打包、测试发现、文档命令、脚本 bootstrap 和统一配置约束，使新的 `src` 布局可以稳定支持本地开发、手动 smoke 和自动测试。
- **BREAKING**: 现有 `from trpg_py ...` 导入路径、`smoke/test_*.py` 脚本路径以及 `tests/` 测试发现路径将切换到新的 `augury` + `src/` 布局。

## 功能 (Capabilities)

### 新增功能
- `src-project-layout`: 定义仓库采用 `src/` 作为唯一 Python 源码根，并要求 `augury` 包、smoke 脚本和自动测试都在该根下组织。

### 修改功能
- `engine-package-layout`: 将核心运行时包命名空间从 `trpg_py.engine` 切换为 `augury.engine`，并要求实现落在 `src/augury/` 下。
- `root-api-layout`: 将稳定顶层 API 从 `trpg_py` 切换为 `augury`，并保持包根目录只暴露精简稳定入口。
- `store-package-layout`: 将状态存储包命名空间从 `trpg_py.store` 切换为 `augury.store`，并同步更新兼容辅助入口约束。
- `project-config`: 将统一配置的包内治理范围从 `trpg_py` 切换为 `augury`，并更新 smoke 默认 world state 对应的新脚本路径。
- `smoke-test-layout`: 将手动集成验证目录从根级 `smoke/` 切换到 `src/smoke/`，并明确自动测试目录为 `src/tests/`。
- `demo-runner`: 将 demo 运行器入口从 `smoke/test_engine.py` 切换到 `src/smoke/test_engine.py`。
- `agent-planner`: 将 planner 公共命名空间切换到 `augury.agent`，并将 smoke 入口切换到 `src/smoke/test_planner.py`。
- `planner-execution-smoke`: 将 planner 到 engine 的端到端 smoke 入口切换到 `src/smoke/test_planner_engine.py`。
- `agent-search-tool`: 将 search 工具导入命名空间切换到 `augury.agent.tools`，并将 smoke 入口切换到 `src/smoke/test_search.py`。
- `fetch-keys-tool`: 将 `list` 工具导入命名空间切换到 `augury.agent.tools`，并将 smoke 入口切换到 `src/smoke/test_fetch_keys.py`。
- `reads-tool`: 将 `read` 工具导入命名空间切换到 `augury.agent.tools`，并将 smoke 入口切换到 `src/smoke/test_reads.py`。
- `grep-tool`: 将 `grep` 工具导入命名空间切换到 `augury.agent.tools`，并将 smoke 入口切换到 `src/smoke/test_grep.py`。
- `lint-tool`: 将 `lint` 工具导入命名空间切换到 `augury.agent.tools`。

## 影响

- 受影响代码：`trpg_py/`、`smoke/`、`tests/` 的全部 Python 模块与脚本导入路径；`pyproject.toml`；README 和开发命令说明。
- 受影响规范：新增 `specs/src-project-layout/spec.md`，并增量修改 package layout、smoke layout、planner/tool smoke 与 project config 相关规范。
- 受影响使用方式：开发者后续将通过 `augury` 作为唯一导入命名空间，并通过 `src/smoke/` 与 `src/tests/` 运行手动验证和自动测试。
