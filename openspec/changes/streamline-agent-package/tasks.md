## 1. Root Shim 清理

- [x] 1.1 识别并删除 `src/augury/agent/` 包根中仅做简单转发的 shim 文件，例如 `runtime.py`、`context_eval.py`、`evals.py`、`cli_ask.py`、`state_loader.py`、`planner_runtime_guards.py`。
- [x] 1.2 保持 `src/augury/agent/__init__.py` 作为稳定公共入口，并确认 `orchestrate.py`、`models.py`、`subagents/`、`tools/`、`utils/` 仍覆盖必要能力。

## 2. 导入与测试迁移

- [x] 2.1 全仓更新对被删除 root shim 的直接导入，切换到 `augury.agent` 包根、`augury.agent.orchestrate` 或 `augury.agent.utils.*` 等正式路径。
- [x] 2.2 更新相关测试、patch 目标和辅助代码，确保仓库内部不再依赖将被删除的 shim 路径。

## 3. 文档与验证

- [x] 3.1 更新 `src/augury/agent/AGENTS.md` 与相关说明文字，明确 root shim 已删除、`utils` 是 helper 的正式落点。
- [x] 3.2 运行与 agent 包收口相关的最小测试或验证脚本，确认删除 shim 后 planner 主链路和 eval helper 未回归。
