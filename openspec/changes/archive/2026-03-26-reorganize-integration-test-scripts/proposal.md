## 为什么

当前仓库根目录同时承载了正式入口、手动 smoke 脚本和集成测试脚本，例如 `main.py`、`test_fetch_keys.py`、`test_search.py`。随着 planner 进入实现阶段，这种布局会让“哪些文件是给人手动跑的集成测试，哪些是正式入口”越来越不清晰，也不利于新增 planner 效果验证脚本。

现在需要把这些可执行脚本收拢为明确的 smoke 测试入口：将 demo 入口重命名为 `test_engine`，把根目录下以 `test` 开头的脚本移动到统一的 `smoke/` 目录，并补一条可直接观察 planner 效果的集成测试脚本，方便后续持续验证 planner 输出质量。

## 变更内容

- 新增 smoke 脚本布局能力，定义仓库中手动运行的验证脚本必须集中放在 `smoke/` 目录中，而不是继续散落在根目录。
- 调整 demo runner 入口约束，将当前 `main.py` 风格的 demo 脚本重命名为 `test_engine.py` 并迁入 `smoke/` 目录。
- 调整现有 `fetch_keys` 演示脚本位置要求，使其从根目录迁入 `smoke/` 目录，并保持可手动运行。
- 调整现有 `search` 手动测试脚本位置要求，使其从根目录迁入 `smoke/` 目录，并保持可手动运行。
- 为 planner 增加一个可直接运行的集成测试脚本，用于观察 `ready/needs_human/blocked` 等效果，而不只依赖单元测试。
- **BREAKING**: 现有依赖 `python main.py ...`、`python test_fetch_keys.py ...`、`python test_search.py ...` 的手动运行方式将切换到新的集成测试目录和脚本名。

## 功能 (Capabilities)

### 新增功能
- `smoke-test-layout`: 定义可手动运行的 smoke 脚本目录、命名约定以及根目录脚本收敛规则。

### 修改功能
- `demo-runner`: 将 demo 脚本入口从 `main.py` 切换为 `smoke/test_engine.py`。
- `fetch-keys-tool`: 将 `fetch_keys` 演示脚本迁入 `smoke/` 目录并更新运行方式。
- `agent-search-tool`: 将 search 手动测试脚本迁入 `smoke/` 目录并更新运行方式。
- `agent-planner`: 新增 planner 效果 smoke 脚本的可运行要求。

## 影响

- 受影响代码：`main.py`（将被重命名/迁移）、根目录现有 `test*.py` 脚本、可能新增的集成测试目录与 planner 脚本。
- 受影响规范：新增 `specs/smoke-test-layout/spec.md`，并增量修改 `specs/demo-runner/spec.md`、`specs/fetch-keys-tool/spec.md`、`specs/agent-search-tool/spec.md`、`specs/agent-planner/spec.md`。
- 受影响测试与文档：需要更新 README、脚本运行说明以及与新路径匹配的测试。
- 受影响使用方式：开发者今后将通过统一的 `smoke/` 目录执行 engine/search/fetch_keys/planner 的手动验证脚本。
