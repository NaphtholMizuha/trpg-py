## 为什么

当前 planner 面向 state 的工具命名是 `fetch_keys` 与 `reads`。这套命名更贴近实现细节而不是 LLM 的常见心智模型，导致 prompt、日志、smoke 输出和人工排障时都需要额外做“它其实就是 list/read”这层翻译。与此同时，`no_match` 目前只告诉调用方“没找到”，却没有给出相近候选路径，planner 很容易围绕错误前缀或错误层级反复试探。

## 变更内容

- 将 planner 默认状态工具的公开语义从 `fetch_keys` / `reads` 收敛为 `list` / `read`。
- 保持底层仍复用现有 `store.keys` 与 `store.reads` 语义，不引入第二套 state 访问实现。
- 在 `list` 与 `read` 返回 `status=no_match` 时增加建议路径或相近候选，帮助 planner 和开发者更快收敛到正确路径。
- 更新 planner prompt、日志、smoke 脚本与相关测试，使默认工具心智模型统一为 `list/read/search/lint`。
- **BREAKING**: `trpg_py.agent.tools` 中原本面向调用方暴露的 `fetch_keys` / `reads` 工具名称与默认 planner prompt 语义将发生调整；依赖旧工具名的调用点、测试和文档需要同步迁移或兼容。

## 功能 (Capabilities)

### 新增功能

无

### 修改功能

- `fetch-keys-tool`: 将面向调用方的工具语义改为 `list`，并在无命中时返回建议路径。
- `reads-tool`: 将面向调用方的工具语义改为 `read`，并在无命中时返回建议路径。
- `agent-planner`: 将 planner 默认 state 工具心智模型、prompt 与日志语义更新为 `list/read`，并要求 planner 可消费 no-match 建议路径帮助收口。

## 影响

- `trpg_py/agent/tools/fetch_keys.py`、`trpg_py/agent/tools/reads.py` 及其导出入口
- `trpg_py/agent/planner.py`、planner prompt 模板、planner smoke 脚本
- 相关单元测试、smoke 测试、日志断言与文档说明
- 可能涉及对旧工具名的兼容策略或迁移说明
