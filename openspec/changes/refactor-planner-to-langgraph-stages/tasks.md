## 1. Graph 与中间产物

- [x] 1.1 设计并实现 planner graph state，以及轻量 `EvidenceBundle` 数据结构，确保其只承载证据小结、关键事实、缺口、假设和来源路径
- [x] 1.2 将现有 planner 主循环重构为显式 LangGraph 工作流，并保留现有对外 `PlannerRequest` / `PlannerResult` 接口兼容层

## 2. 两阶段 Agent

- [x] 2.1 实现 `evidence_agent` `create_agent()` 节点，只挂载 `search`、`list`、`read`，输出 `EvidenceBundle` 或触发 HITL
- [x] 2.2 实现 `dsl_agent` `create_agent()` 节点，只挂载 `lint`，并基于 `EvidenceBundle` 生成候选 `TaskDocument`
- [x] 2.3 为 `dsl_agent` 加入 `lint` 驱动的有限修复闭环和独立预算/停止条件

## 3. HITL 与恢复

- [x] 3.1 把 `needs_human` 重构为 graph interrupt/resume 语义，同时保持当前对外 `status=needs_human` 结果兼容
- [x] 3.2 更新 thread/checkpointer 接线，使恢复后的 planner 能继续同一条 staged workflow，而不是重启整轮规划

## 4. Smoke 与可观察性

- [x] 4.1 更新 `smoke/test_planner.py` 和 `smoke/test_planner_engine.py`，展示信息获取、DSL、HITL 和 execution 等阶段摘要
- [x] 4.2 更新日志和 debug 负载，使开发者可以区分 graph 节点、EvidenceBundle 摘要和阶段恢复路径

## 5. 验证

- [x] 5.1 添加单元测试，覆盖 `evidence_agent` 阶段 `needs_human` 暂停、resume 后继续进入 `dsl_agent` 阶段的路径
- [x] 5.2 添加单元测试，覆盖 `dsl_agent` 通过 `lint` 自修、修复耗尽以及转入 `needs_human/blocked` 的路径
- [x] 5.3 运行相关测试与 smoke，验证 staged planner 仍保持现有对外接口兼容，并能正确展示 graph 阶段
