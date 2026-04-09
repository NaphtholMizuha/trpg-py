## 为什么

上一轮重构虽然把 `runtime.py` 迁成了 `orchestrate.py`，也把一批 helper 收进了 `agent/utils/`，但 `src/augury/agent/` 包根现在仍然保留着一层过渡 shim：`runtime.py`、`context_eval.py`、`evals.py`、`cli_ask.py`、`state_loader.py`、`planner_runtime_guards.py` 这些文件大多只是转发到真正实现。这样会让维护者误以为这些根级模块仍然是长期入口，也让目录长期停留在“已经迁移，但还没真正收口”的状态。

现在需要继续收紧 `augury.agent` 的包布局，把已经没有长期价值的 root shim 删掉，只保留真正长期存在的入口与实现模块。这样可以让 `agent` 目录真正表达长期架构，而不是把过渡兼容层继续固化成新的复杂度。

## 变更内容

- **BREAKING** 继续精简 `src/augury/agent/` 包根，只保留长期公共入口、核心模型、主 orchestration 模块及明确的子目录；删除没有长期价值的根级兼容 shim 或冗余模块。
- 明确 `agent/utils/` 已经是当前 helper 的正式落点，本次不再继续细分 `utils/` 内部目录。
- 清理 `agent` 包内已经没有真实调用价值或只剩历史过渡意义的 root shim，必要时直接删除，而不是继续保留一层薄转发。
- 更新文档、OpenSpec 规范与测试，明确哪些模块是正式入口，哪些根级 shim 必须删除，以及调用方应该转向哪些稳定路径。

## 功能 (Capabilities)

### 新增功能
<!-- 无 -->

### 修改功能
- `agent-planner`: 收紧 planner 在 `augury.agent` 命名空间下的公开入口约束，要求对外 API 通过稳定包根暴露，而不是继续依赖根级 shim 文件。
- `delegating-agent-runtime`: 调整 delegating runtime 的包内组织要求，明确过渡兼容层必须及时清理，长期目录应只保留真正承担编排、子 agent 和工具职责的模块。
- `src-project-layout`: 细化 `src/augury/agent/` 的包内收敛要求，要求 helper 已进入辅助目录后，包根的过渡模块必须及时删除，不得长期保留双重真相。

## 影响

- 受影响代码将包括 `src/augury/agent/__init__.py`、`src/augury/agent/orchestrate.py`、当前根级兼容 shim、相关测试和文档。
- 任何仍然依赖 `augury.agent.runtime`、`augury.agent.context_eval`、`augury.agent.evals`、`augury.agent.cli_ask` 等过渡入口的内部调用都需要迁移，外部兼容策略也需要重新评估。
- 该变更主要聚焦删除和收口，而不是继续扩展目录层级，因此需要特别明确哪些路径保留、哪些路径移除，避免仓库长期停留在“半兼容、半新结构”的状态。
