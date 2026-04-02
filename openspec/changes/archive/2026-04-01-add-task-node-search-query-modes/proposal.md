## 为什么

当前 `task_node` 在规则优先任务中调用 `search` 时，被 prompt 统一引导为使用中文 HyDE 风格查询。这对模糊规则场景有帮助，但在存在明确规则术语时会削弱词面锚点，导致 `火球术`、`反制法术`、`借机攻击` 等查询更容易命中语义相似条目而非目标规则本体。

## 变更内容

- 为单一 `search` 工具引入 `term`、`balanced`、`semantic` 三种查询模式。
- 调整 `task_node` prompt，不再要求所有规则检索都使用 HyDE 风格查询，而是先判断是否存在明确规则术语，再选择模式。
- 增加关于 query planning、query formulation 和 evidence interpretation 的提示词约束与 few-shot 示例。
- 保持底层检索器仍为现有 hybrid + rerank 流程，先验证 query 组织方式与模式选择是否足以改善规则条目命中质量。

## 功能 (Capabilities)

### 新增功能

### 修改功能
- `agent-search-tool`: search 工具的输入契约将增加查询模式，并允许调用方表达术语定位、术语加结算、纯语义检索三种意图。
- `planner-langgraph-workflow`: task_node 的规则检索提示词将从统一 HyDE 查询改为基于 `term`、`balanced`、`semantic` 三模式的 query planning。

## 影响

- `config/prompts/planner_task_node_system.txt`
- `config/prompts/planner_task_node_user.txt`
- `src/augury/planner/tools/search.py`
- `src/augury/rag/retriever.py`
- `src/tests/test_agent_search.py`
- `src/tests/test_smoke_scripts.py` 或相关 smoke case
