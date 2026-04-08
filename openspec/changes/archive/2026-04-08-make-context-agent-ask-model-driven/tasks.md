## 1. Prompt 与规范收敛

- [x] 1.1 更新 Context Agent 相关 prompt，明确 ask 是否触发必须由模型根据证据缺口自主决定
- [x] 1.2 补齐 ask tool 与 agent-planner 的增量规范，禁止宿主代码保留按缺口类别硬编码的 ask 策略

## 2. Context Agent 重构

- [x] 2.1 重构 `src/augury/agent/subagents/context_agent.py`，移除 `_ask_for_actor_if_needed`、`_ask_for_target_if_needed`、`_ask_for_area_point_if_needed`
- [x] 2.2 调整 Context Agent 主控制流，让模型直接决定返回 ask、继续取证或返回阻塞结果
- [x] 2.3 将 `_analyze_intent(...)` 或其等价逻辑降级为推理支架，禁止任何分析字段直接驱动 ask

## 3. 测试与评测修正

- [x] 3.1 更新 Context Agent 相关单测，移除对固定 ask 分支和特定函数存在性的依赖
- [x] 3.2 更新 eval 与集成测试断言，改为验证 ask 的结构合法性、interrupt/resume 行为和模型驱动决策边界
- [x] 3.3 运行相关测试并手动验证典型歧义场景，确认 ask 触发不再由宿主代码检测决定
