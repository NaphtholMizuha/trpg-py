## 1. 包布局重组

- [x] 1.1 新增 `src/augury/agent/utils/`，并将当前包根下的 CLI、eval、state loading 与其他辅助模块迁移到该目录或其等价子目录。
- [x] 1.2 将 `src/augury/agent/runtime.py` 重命名为 `src/augury/agent/orchestrate.py`，并保持主 agent orchestration 实现完整迁移。
- [x] 1.3 更新 `src/augury/agent/__init__.py` 与包内导入，确保 `augury.agent` 包根继续暴露稳定公共 API。

## 2. 兼容与回归收敛

- [x] 2.1 全仓更新对旧 `augury.agent.runtime` 和已迁移 helper 模块路径的直接导入，收敛到新布局。
- [x] 2.2 评估是否需要为旧路径保留短期兼容 shim；若需要，补充最小转发层并明确其过渡性质。
- [x] 2.3 补充或更新导入相关测试，验证重构后 `create_planner`、模型类型和 eval helper 仍可通过 `augury.agent` 正常访问。

## 3. 文档与规范同步

- [x] 3.1 更新 `src/augury/agent/AGENTS.md`，使模块边界、文件名和读码顺序反映新的包布局。
- [x] 3.2 更新受影响的 OpenSpec 引用、说明文字和实现注释，移除把 `runtime.py` 和根目录平铺结构视为长期真相的描述。
- [x] 3.3 运行与 agent 包重组相关的最小测试或验证脚本，确认新路径、re-export 和 planner 主链路未回归。
