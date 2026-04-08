## 为什么

当前 Context Agent 的 ask 触发条件部分由宿主代码硬编码决定，例如 `_ask_for_actor_if_needed`、`_ask_for_target_if_needed` 和 `_ask_for_area_point_if_needed` 会在特定解析分支下直接发起 ask。这样会把“是否需要 ask”从模型的推理职责降级为代码分支检测，导致 agent 行为被实现细节预先规定，而不是由模型根据证据缺口自主决定。

这在当前阶段已经成为架构问题。随着 ask 被提升为可中断工具，系统更需要统一一个清晰边界：代码只提供 ask 工具与恢复协议，是否 ask、问什么、是否继续取证，必须由模型输出决定，而不是继续在 Python 分支里固化若干“缺执行者就问”“目标不唯一就问”的局部规则。

## 变更内容

- 移除 Context Agent 中按 actor、target、area point 分类的代码级 ask 触发函数与对应控制流。
- 改为由模型在单次或多次推理中自主决定是否生成结构化 ask 请求，而宿主代码只负责承载 ask 工具契约、interrupt/resume 语义和结果回填。
- 收紧 ask 相关提示词与 agent 合同，明确 ask 的触发必须来自模型对证据缺口的判断，而不是来自宿主代码对特定字段缺失的检测。
- 调整评测与测试，使其验证“模型可以决定 ask”，而不是继续把某些 ask 分支当成实现前提。

## 功能 (Capabilities)

### 新增功能
- `agent-ask-tool`: 规定 ask 触发权必须属于模型推理结果，宿主代码只提供统一 ask 契约、展示与恢复能力，不得继续内置特定 ask 决策分支。

### 修改功能
- `agent-planner`: planner / Context Agent 的上下文收集链路改为由模型自主决定是否 ask，禁止宿主代码继续根据 actor、target 或 area point 等具体缺口直接触发 ask。

## 影响

- 受影响代码包括 `src/augury/agent/subagents/context_agent.py`、相关 ask tool 适配层、Context Agent prompt，以及围绕 ask interrupt / eval 的测试。
- 需要重新定义 Context Agent 与 ask tool 的职责边界：代码负责协议与恢复，模型负责 ask 决策。
- 现有依赖 `_ask_for_actor_if_needed`、`_ask_for_target_if_needed` 等函数存在的测试需要改写，避免把实现细节固化成长期行为。
