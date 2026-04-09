## 上下文

`src/augury/agent/` 上一轮已经完成了一次明显的边界收敛：

- 主编排入口迁移到了 `orchestrate.py`
- 评测、CLI、状态加载等辅助代码迁到了 `utils/`
- 包根保留 `__init__.py`、`models.py`、`orchestrate.py`、`subagents/`、`tools/` 与若干兼容 shim

但当前包根仍然留着一层明显的过渡状态：`runtime.py`、`context_eval.py`、`evals.py`、`cli_ask.py`、`state_loader.py`、`planner_runtime_guards.py` 这些文件大多只做简单转发。它们在短期迁移阶段有价值，但继续长期保留会产生两个问题：

1. 维护者无法快速分辨哪些文件是长期真相，哪些只是历史兼容层；
2. 包根继续承载“旧路径”和“新路径”双重真相，削弱上一轮重构想建立的结构边界。

用户已经明确这次不希望继续折腾 `utils/` 内部布局，重点是删掉 root shim。因此本次设计必须刻意聚焦：只收口根级过渡层，不再扩散到新的目录细分。

## 目标 / 非目标

**目标：**

- 删除 `src/augury/agent/` 包根下没有长期价值的兼容 shim。
- 将仓库内部代码与测试切换到 `augury.agent` 包根、`augury.agent.orchestrate` 或 `augury.agent.utils.*` 等正式路径。
- 保持 `augury.agent` 包根公共 API 稳定，但不再通过根级 shim 文件维持多余入口。
- 更新文档和规范，使“包根只保留长期入口”成为新的明确真相。

**非目标：**

- 本次不继续细分 `agent/utils/` 内部目录。
- 本次不重写 `ContextAgent`、`ResolutionAgent`、`tools/` 或 `models.py` 的核心行为。
- 本次不引入新的 helper 子包或新的 facade 层。
- 本次不承诺兼容所有历史内部导入路径；对于仓库内部已知调用，直接迁移优先于继续兼容。

## 决策

### 决策 1：删除根级兼容 shim，而不是继续维持转发

本次应删除以下类型的根级 shim：

- `runtime.py`
- `context_eval.py`
- `evals.py`
- `cli_ask.py`
- `state_loader.py`
- `planner_runtime_guards.py`

这些模块的长期替代路径分别是：

- `orchestrate.py`
- `utils.context_eval`
- `utils.evals`
- `utils.cli_ask`
- `utils.state_loader`
- `utils.planner_runtime_guards`

选择理由：

- 这些文件的主要价值已经完成，即帮助上一轮迁移过渡。
- 如果继续保留，会使“根级 shim”被误读为正式入口。
- 删除它们能让包根结构立即收口。

备选方案：

- 永久保留薄转发。未采用，因为这会把过渡状态固化为长期复杂度。

### 决策 2：正式公开入口只保留 `augury.agent` 包根与少量实现模块

长期导入真相应收敛为：

- 外部公共 API：`augury.agent`
- 主编排实现：`augury.agent.orchestrate`
- 辅助模块：`augury.agent.utils.*`
- 子 agent / 工具实现：`augury.agent.subagents.*`、`augury.agent.tools.*`

选择理由：

- `augury.agent` 包根继续承担稳定 public facade
- `orchestrate.py` 保留为明确的内部主入口
- `utils.*` 明确表达“这里是 helper 真相”，而不是包根继续承担双重角色

备选方案：

- 让外部调用直接导入 `utils.*` 作为唯一入口。未采用，因为公共入口仍应优先通过包根暴露。

### 决策 3：仓库内部调用必须优先迁移，而不是依赖兼容层

对于仓库内部的源码、测试和脚本，本次应直接改到新路径，不应继续通过被删除 shim 间接访问实现。

选择理由：

- 仓库内部最容易一次性完成迁移。
- 如果连内部代码都继续依赖 shim，就无法真正删除它们。

备选方案：

- 只删除外部文档引用，内部代码继续走 shim。未采用，因为这样无法收口。

## 风险 / 权衡

- [删除 shim 后可能暴露漏改的导入] → 通过全仓搜索、编译和针对 agent 包的回归测试发现残留引用。
- [某些外部用户可能依赖历史内部路径] → 本次以仓库内部真相收口为先，并通过 `augury.agent` 包根保留正式公共 API。
- [包根变薄后，维护者需要适应新的 helper 路径] → 通过更新 AGENTS.md 和规范说明新导入约定。

## 迁移计划

1. 更新规范，明确根级 shim 不能作为长期真相保留。
2. 全仓替换对 `augury.agent.runtime`、`augury.agent.context_eval`、`augury.agent.evals` 等 shim 的直接依赖。
3. 删除根级 shim 文件，只保留 `__init__.py`、`models.py`、`orchestrate.py`、`subagents/`、`tools/`、`utils/`。
4. 更新 AGENTS.md、相关注释和说明文字。
5. 运行最小回归测试，确认 planner 主链路和 eval helper 不回归。

回滚策略：

- 如果删除某个 shim 后发现仍有必要兼容的调用面，可在实现阶段重新评估单独恢复一个有限 shim，但默认目标仍是彻底删除。

## 开放问题

- 是否需要为少数仓库外消费者保留迁移说明文档，说明旧 shim 对应的新路径。
