## 上下文

当前 `src/augury/agent/` 包根同时放着几类不同职责的模块：

- `runtime.py`：主 agent 编排入口与默认装配
- `models.py`：对外共享的数据模型
- `cli_ask.py`、`context_eval.py`、`evals.py`：交互与评测辅助
- `state_loader.py`、`planner_runtime_guards.py`：实现支撑工具
- `subagents/`、`tools/`：已经具备较清晰子目录边界

这里最大的结构性问题不是“文件多”，而是“角色混放”。维护者打开 `augury.agent` 包根时，很难一眼分辨哪些文件属于长期公共入口，哪些只是支持性 helper。尤其 `runtime.py` 这个名字过于泛化，但它实际承担的是主 agent 的 orchestration 真相；同时多种 eval/CLI/state helper 平铺在根目录，也让 `agent` 包根显得像临时落脚点，而不是稳定命名空间。

这次设计希望在不改变 planner 外部能力目标的前提下，重新表达 `agent` 包的内部边界：

- 包根保留清晰且少量的长期入口；
- `models.py` 继续作为高频共享的数据契约模块留在根目录；
- 主编排入口以 `orchestrate.py` 命名，直接体现职责；
- 其余支撑性模块收敛到 `agent/utils/`，避免包根继续承担杂项收纳职责；
- `subagents/` 与 `tools/` 继续保持独立目录，不与 `utils/` 混淆。

## 目标 / 非目标

**目标：**

- 让 `src/augury/agent/` 的目录结构直接表达主入口、数据模型、子 agent、工具和辅助模块的边界。
- 将当前 `runtime.py` 更名为 `orchestrate.py`，使文件名与主 agent orchestration 职责一致。
- 将包根下除 `models.py` 外的辅助模块迁移到 `agent/utils/` 或更合适的子目录，并统一更新导入。
- 保持 `augury.agent` 包根的稳定公共 API，使调用方优先依赖 re-export，而不是依赖内部文件位置。
- 在文档、规范和测试中把新的包布局定义成长期真相。

**非目标：**

- 本次不重写 `ContextAgent`、`ResolutionAgent` 或 `tools/` / `subagents/` 的核心行为。
- 本次不改变 planner 的结构化输入输出 schema。
- 本次不要求一次性删除所有旧导入路径；若存在兼容需要，可以保留短期 shim，但不能让 shim 成为长期真相。
- 本次不把 `models.py` 继续拆散到更多子目录。

## 决策

### 决策 1：`runtime.py` 重命名为 `orchestrate.py`

`src/augury/agent/runtime.py` 的职责是主 agent orchestration：装配默认工具、注册子 agent、通过 `delegate` 串起 Context Agent 与 Resolution Agent。因此应将该模块更名为 `orchestrate.py`，并把相关实现与引用迁移过去。

选择理由：

- “runtime” 过于宽泛，无法体现这是主编排入口。
- “orchestrate” 能更直接对应主 agent 的长期职责和 `delegate` 编排心智。
- 可以降低维护者对“agent runtime”与“具体 orchestration 入口”之间的混淆。

备选方案：

- 保持 `runtime.py` 不变。未采用，因为这正是当前命名误导的来源。
- 改名为 `planner.py` 或 `main_agent.py`。未采用，因为前者弱化了 orchestration 语义，后者又把文件与具体角色耦合得更死。

### 决策 2：包根只保留公共入口、高频模型与已分层目录

重构后，`src/augury/agent/` 包根应优先保留以下内容：

- `__init__.py`
- `models.py`
- `orchestrate.py`
- `subagents/`
- `tools/`
- `utils/`

其中 `cli_ask.py`、`context_eval.py`、`evals.py`、`state_loader.py`、`planner_runtime_guards.py` 等辅助模块迁移到 `utils/`。如果后续发现某类 helper 已经形成稳定子域，再从 `utils/` 继续细分；但第一步先停止把它们长期平铺在包根。

选择理由：

- 包根应主要承载命名空间入口，而不是杂项实现。
- `models.py` 是高频共享契约，保留在包根有利于导入直觉。
- `subagents/` 与 `tools/` 已有稳定边界，不必强行迁入 `utils/`。

备选方案：

- 所有文件都收进 `utils/`。未采用，因为这会把真正的核心入口也埋进“工具箱”式目录，反而削弱结构表达。
- 每一类 helper 先拆成多个新子包。未采用，因为首轮目标是先收束根目录复杂度，而不是一次性过度细分。

### 决策 3：通过 `augury.agent` 包根 re-export 维持稳定公共 API

重构后，外部调用应继续优先通过 `augury.agent` 包根访问 `create_planner`、`PlannerRequest`、`PlannerResult`、eval helper 等公共符号。包内文件移动或更名不应成为外部调用方必须关心的事实。

实现上可以：

- 直接更新 `__init__.py` 指向新模块路径；
- 在必要时保留窄兼容 shim，例如旧模块仅转发到新模块并标注待移除。

选择理由：

- 允许内部布局演进，而不把外部用户绑死在内部文件路径上。
- 与现有 `augury.agent` 命名空间规范保持一致。

备选方案：

- 要求所有调用方同步改用新的内部文件导入。未采用，因为这会把实现重构变成外部 API 破坏。

### 决策 4：以“先移动、再清理兼容层”的顺序迁移

迁移顺序应当先建立新目录与新模块名，再更新内部导入、测试与文档，最后决定是否保留短期兼容文件。这样可以把风险控制在“路径重写”层面，减少一次性大规模逻辑改动。

建议顺序：

1. 新增 `agent/utils/`
2. 将根目录 helper 文件迁入 `utils/`
3. 将 `runtime.py` 内容迁入 `orchestrate.py`
4. 更新 `__init__.py`、包内导入、测试与文档
5. 视兼容需求保留或删除旧路径 shim

选择理由：

- 降低 refactor 时的循环导入和半迁移状态风险。
- 让测试可以在每一阶段验证公开 API 仍然可用。

备选方案：

- 一次性边移动边改逻辑。未采用，因为难以定位回归来源。

## 风险 / 权衡

- [内部路径移动导致导入回归] → 通过先更新包根 re-export、补充导入相关测试并在必要时保留短期 shim 缓解。
- [`utils/` 过度膨胀，成为新的杂物间] → 先只收纳当前根目录 helper，并在设计中明确 `orchestrate`、`models`、`subagents`、`tools` 不能继续下沉到 `utils/`。
- [现有文档和 AGENTS 引用旧文件名] → 在实现任务中显式包含文档与规范同步更新，避免代码先变、说明滞后。
- [对外用户可能已经直接导入内部模块] → 通过兼容层或一次性全仓导入替换，尽量降低短期破坏面。

## 迁移计划

1. 先更新 OpenSpec 规范，明确 `agent` 包布局和 orchestration 模块命名的新约束。
2. 在代码中创建 `src/augury/agent/utils/`，迁移现有根目录 helper 文件。
3. 将 `runtime.py` 重命名为 `orchestrate.py`，并更新所有直接导入点。
4. 更新 `src/augury/agent/__init__.py`，确保公共 API 仍从 `augury.agent` 暴露。
5. 更新 `AGENTS.md`、测试、eval 脚本和其他文档引用。
6. 根据兼容需要决定是否短期保留旧路径 shim；若保留，必须在代码中明确其过渡性质。

回滚策略：

- 如果迁移过程中发现外部依赖面比预期更广，可先保留旧模块作为只转发的兼容层，再分阶段清理。
- 如果 `utils/` 布局在实现中暴露出更合适的专用子目录，也可以在不改变 proposal 目标的前提下细化落点，但不得回退到包根平铺。

## 开放问题

- `context_eval.py` 与 `evals.py` 是否在第一轮都进入统一 `utils/`，还是进一步拆成 `utils/evals/` 子目录。
- `planner_runtime_guards.py` 是否继续保留现名放在 `utils/`，还是顺手一并做更语义化命名。
- 是否需要为旧的 `augury.agent.runtime` 保留一个短期兼容文件，还是可以在仓库内一次性完成全部导入切换。
