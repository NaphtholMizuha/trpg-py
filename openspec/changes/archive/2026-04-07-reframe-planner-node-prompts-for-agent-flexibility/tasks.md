## 1. 规范与提示词契约

- [x] 1.1 更新 `openspec/specs/planner-node-prompts/spec.md`，同步 `task_node` 启发式 prompt 与 `dsl_node` primitive 语义化 prompt 的正式需求
- [x] 1.2 更新 `openspec/specs/planner-langgraph-workflow/spec.md`，移除与固定任务原型覆盖、固定查询模式仪式强绑定的旧约束
- [x] 1.3 审阅现有 OpenSpec 变更与归档设计，确认没有遗留规范继续要求 `task_node` 以 upfront 分类作为主入口

## 2. Task Node Prompt 重写

- [x] 2.1 重写 `config/prompts/planner_task_node_system.txt`，将主线改为执行目标、关键前提、证据缺口和安全状态绑定
- [x] 2.2 重写 `config/prompts/planner_task_node_user.txt`，减少“分类介绍式” requirements，保留必要护栏与结构化输出要求
- [x] 2.3 收紧 `task_node` prompt 对 `grep` / `search` 的描述，使其体现高优先级原则而不是固定仪式流程
- [x] 2.4 重新设计 `task_node` few-shot（若保留），使其示范取证与缺口暴露，而不是覆盖固定类别清单

## 3. Dsl Node Prompt 重写

- [x] 3.1 重写 `config/prompts/planner_dsl_node_system.txt`，显式解释 `select`、`check`、`damage`、`heal`、`resource`、`effect`、`state` 的职责与边界
- [x] 3.2 重写 `config/prompts/planner_dsl_node_user.txt`，把 lowering 原则改成“基于 primitive 语义的自由合理组合 + template/lint 收敛”
- [x] 3.3 调整 `dsl_node` prompt 对 `template` 的定位，确保其是 shape 参考而不是唯一组合来源
- [x] 3.4 调整 `dsl_node` prompt 对 `lint` 的定位，确保其继续作为诊断与收敛工具而不是替代原语理解的控制器

## 4. 测试与验证

- [x] 4.1 更新 `src/tests/test_planner_workflow.py`，把 prompt 断言从旧的分类口号改为新的边界、护栏和 primitive 语义要求
- [x] 4.2 增加或更新测试，验证 `task_node` prompt 不再要求固定任务原型覆盖数量和固定三选一 search mode 仪式
- [x] 4.3 增加或更新测试，验证 `dsl_node` prompt 已明确 primitive 职责、组合方式以及 `template`/`lint` 的新定位
- [x] 4.4 运行相关单元测试与 smoke，重点检查范围法术、混合任务和纯状态查询场景没有明显退化
