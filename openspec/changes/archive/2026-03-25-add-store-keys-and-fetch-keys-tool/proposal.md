## 为什么

当前 planner agent 已经有 `search` 能力，但仍缺少“查看当前 state 可引用路径”的基础工具，LLM 在生成 `TaskDocument` 时容易出现路径猜测和引用错误。为了降低路径幻觉并提升可执行率，系统需要在 `store` 层提供标准化 key 枚举能力，并在 `agent.tools` 层提供可直接调用的 `fetch_keys` 工具。

## 变更内容

- 修改 `state-store` 能力：在现有点路径读写接口基础上，新增 key 枚举接口，支持全量枚举与按范围枚举。
- 新增 `fetch-keys-tool` 能力：在 `trpg_py.agent.tools` 中提供 `fetch_keys` 工具封装，并保持结构化返回语义。
- 明确 `keys` / `fetch_keys` 的输入输出契约，包括 `prefix`、`limit`、`cursor` 等范围控制能力和空结果语义。
- 明确 `fetch_keys` 仅提供路径可见性，不承担规则推理或状态写入职责。
- 增加面向人的可运行测试脚本要求，确保新能力的行为可以直接观察和演示。

## 功能 (Capabilities)

### 新增功能
- `fetch-keys-tool`: 提供面向 agent 的路径枚举工具，包装 `store.keys` 能力并可集成到工具调用链路中。

### 修改功能
- `state-store`: 扩展统一状态存储接口，新增 key 枚举能力与范围控制语义。

## 影响

- `trpg_py.store` 的公开接口会新增 `keys`（及相关导出同步）。
- `trpg_py.agent.tools` 会新增 `fetch_keys` 工具实现与对应输入输出模型。
- planner agent 的工具集将新增一条“路径发现”能力，与 `search` 形成互补。
- 需要新增测试覆盖全量枚举、按范围枚举、空结果和工具包装行为。
- 需要新增一个可直接运行的测试脚本（如 `test_fetch_keys.py`）用于演示新代码能力。
