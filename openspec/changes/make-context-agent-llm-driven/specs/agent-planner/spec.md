## 新增需求

## 修改需求

### 需求:Context Agent 核心执行体必须由 `langchain.create_agent` 驱动
系统必须要求 `src/augury/agent/subagents/context_agent.py` 的核心执行体由 `langchain.create_agent` 创建的 agent 驱动，禁止以手写启发式控制流或手写临时模型循环作为最终长期实现。

#### 场景:默认创建 Context Agent
- **当** planner 以默认依赖装配 Context Agent
- **那么** Context Agent 必须通过 `langchain.create_agent` 产出的 agent 承担核心推理
- **那么** `grep`、`search`、`ask` 必须作为 Context Agent 自身装配的 tools 暴露给该 agent

### 需求:Context Agent 必须通过模型推理决定是否 ask
系统必须让 Context Agent 在上下文收集过程中由真实模型调用根据 prompt、当前证据和已有 ask 响应决定下一步动作。系统禁止继续让 `ContextAgent` 的默认控制流仅依赖类内部的 `_analyze_intent`、实体匹配结果或按缺口类别硬编码的 ask 触发分支。

#### 场景:执行者缺失但 agent 仍可先继续取证
- **当** 当前意图尚未唯一识别执行者
- **那么** Context Agent 必须先通过模型判断是否应继续检索证据、直接阻塞，或发起 ask
- **那么** `ContextAgent` 的类内部默认流程不得仅因 `actor_missing` 为真就直接触发 ask

#### 场景:范围法术缺少爆点
- **当** 范围法术意图缺少爆点或位置描述
- **那么** Context Agent 必须通过模型判断是发起 ask、依据现有目标位置继续推理，还是返回其他结构化结果
- **那么** `ContextAgent` 的类内部默认流程不得仅因命中某个法术名或位置缺失条件就直接构造 ask

#### 场景:prompt 调整影响真实 Context Agent 行为
- **当** 维护者更新 Context Agent 的默认 prompt 模板
- **那么** 这些 prompt 必须参与真实的模型推理链路
- **那么** Context Agent 的后续取证、ask 或完成行为必须能够随之发生变化

## 移除需求
