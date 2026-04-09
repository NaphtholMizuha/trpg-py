## 为什么

当前 `ContextAgent` 的核心分析流程仍然由 `context_agent.py` 内部的 `_analyze_intent`、实体匹配和硬编码 ask 判定驱动；仓库虽然已经存在 `planner_context_agent_system/user` prompt 与 planner 模型配置，但这些资源并没有真正参与 `ContextAgent` 的运行。这使得 Context Agent 很难根据不同语境灵活决定先继续取证、直接阻塞，还是发起 ask，也让后续 prompt 调优和模型评测无法作用到真实链路。

现在需要把 Context Agent 改造成真正的 LLM 驱动子 agent：由模型基于 prompt 和当前证据决定下一步动作，而 `ContextAgent` 自身负责持有并调用 `grep/search/ask` 工具、执行结构化输出校验并组装 `ContextBundle`。这样才能让现有 prompt/config 成为真实运行时契约，并为后续提升上下文收集质量打下基础。

## 变更内容

- **BREAKING** 将 `ContextAgent` 的默认推理真相从类内部硬编码分析逻辑，调整为由配置中的 planner 模型和 context-agent prompt 驱动。
- 要求 `ContextAgent` 的核心执行体基于 `langchain.create_agent` 创建，而不是继续用手写启发式分支或手写临时模型循环作为长期实现。
- 要求 `ContextAgent` 在上下文收集过程中由模型决定是继续调用 `grep/search` 取证、生成结构化 `ask_requests`，还是返回 `ready/blocked` 的 `ContextBundle`。
- 要求运行时真实加载并渲染 `config/prompts/planner_context_agent_system.txt` 与 `planner_context_agent_user.txt`，禁止继续让这些 prompt 仅作为未接线资源存在。
- 为 `ContextAgent` 增加受统一配置驱动的模型调用装配、失败处理与测试替身接口，保证 eval 和单测可以在不触发真实外部请求的情况下验证 LLM 驱动链路。
- 更新 focused eval、测试与相关辅助代码，验证新的 LLM 驱动控制流、prompt 装载行为以及 ask/blocked/ready 三类结果。

## 功能 (Capabilities)

### 新增功能
<!-- 无 -->

### 修改功能
- `agent-planner`: 调整 planner 对外能力，要求默认 Context Agent 由模型驱动完成上下文分析与 ask 决策，而不是继续依赖类内部启发式分支。
- `delegating-agent-runtime`: 调整 Context Agent 的运行时契约，使其通过模型 + `grep/search/ask` 工具循环收集证据并产出结构化 bundle。
- `planner-langgraph-workflow`: 扩展现有“核心节点由 `langchain.create_agent` 驱动”的约束到 Context Agent，避免 delegating agents 体系里出现一个脱离 agent runtime 的特例实现。
- `planner-node-prompts`: 调整 prompt 能力范围，要求 context-agent prompt 文件被真实加载并参与 Context Agent 推理，而不是仅存在于配置与测试夹具中。

## 影响

- 受影响代码主要包括 `src/augury/agent/subagents/context_agent.py`、`src/augury/agent/runtime.py`、prompt/config 读取相关代码、focused eval 与 Context Agent 测试。
- 现有依赖 `_analyze_intent` 与硬编码 ask 控制流的实现将被重构或降级为兼容/回退路径。
- 该变更会让 planner 运行开始依赖已配置的 LLM 调用装配，因此需要明确的测试替身与错误处理，避免单测直接访问外部网络。
