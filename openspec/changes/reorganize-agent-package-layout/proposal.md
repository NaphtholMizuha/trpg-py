## 为什么

当前 `src/augury/agent/` 目录同时承载主编排入口、CLI 交互辅助、eval helper、状态加载和其他杂项工具，模块角色不够清晰。`runtime.py` 实际承担的是主 agent 的 orchestration 入口，但文件名仍然停留在泛化的 `runtime`；而 `cli_ask.py`、`context_eval.py`、`evals.py`、`state_loader.py`、`planner_runtime_guards.py` 这类文件也长期平铺在包根，增加了维护者理解边界和查找职责的成本。

现在需要把 `augury.agent` 的文件组织调整成更清晰的分层：让主编排入口以更准确的 `orchestrate` 命名存在，并把除 `models.py` 之外的辅助模块收敛到 `agent/utils/` 等更合适的位置。这样可以让目录结构更直接表达“公开入口、核心模型、子 agent、工具、辅助代码”的边界，也为后续继续扩展 agent runtime 留出更稳定的包布局。

## 变更内容

- **BREAKING** 将 `src/augury/agent/runtime.py` 重命名为表达主 agent 编排职责的 `orchestrate.py`，并调整相应导入路径与文档引用。
- **BREAKING** 重整 `src/augury/agent/` 包布局，把根目录下除 `models.py` 外的辅助模块迁移到 `agent/utils/` 或其他更合适的子目录，避免继续把 eval、CLI 辅助、状态加载和运行时守卫与公开入口混放。
- 保持 `augury.agent` 作为对外公共命名空间，但明确由包根 re-export 稳定 API，调用方不应被迫依赖重构前的内部文件路径。
- 更新 `AGENTS.md`、OpenSpec 规范和相关测试，要求 `agent` 包布局能直接体现 orchestration 入口与辅助模块的职责分层，而不是继续以历史文件名和散落平铺结构作为事实标准。

## 功能 (Capabilities)

### 新增功能
<!-- 无 -->

### 修改功能
- `agent-planner`: 调整 planner 对外入口的模块组织约束，要求主编排入口以清晰的 orchestration 模块承载，并由包根维持稳定公共 API。
- `delegating-agent-runtime`: 调整 delegating runtime 的实现布局要求，明确主 agent orchestration、子 agent、工具与辅助模块应分层组织，而不是长期挤在 `augury.agent` 包根。
- `src-project-layout`: 细化 `src/augury/agent/` 的包内组织约束，要求 agent 包内的核心入口、数据模型、辅助工具和支持性模块分层收纳。

## 影响

- 受影响代码将包括 `src/augury/agent/runtime.py`、`src/augury/agent/__init__.py`、根目录下的 eval/CLI/state helper 模块、相关导入点、`AGENTS.md` 和测试。
- 任何直接导入 `augury.agent.runtime`、`augury.agent.cli_ask`、`augury.agent.context_eval`、`augury.agent.evals`、`augury.agent.state_loader` 或其他内部文件路径的代码都需要迁移或增加兼容层。
- 该变更主要调整包布局与模块边界，不改变 planner 的目标能力；但它会改变内部文件路径和部分内部导入真相，因此需要明确兼容策略与重构顺序。
