## 为什么

`doc/rag.md` 已经把当前规则知识库的真实组织方式固定为 `trpg_knowledge` 集合上的“父子节点 + dense/sparse 混合检索 + 最小 payload”结构，但现有 `search` 工具仍沿用更早期的 payload 假设，如 `content`、`file`、`parent_content`。如果不把工具契约对齐到当前 RAG schema，search 命中结果就难以稳定返回正确元数据，也无法按 `parent_id` 回收更完整的父级上下文。

## 变更内容

- 将 `search` 工具的检索与返回契约对齐到 `doc/rag.md` 描述的当前知识库 schema，明确默认面向 `trpg_knowledge` 集合及其 `dense` / `sparse` 向量命名工作。
- 要求 `search` 直接消费并返回当前最小 payload 中的稳定字段：`book`、`path`、`doc_type`、`title`、`parent_id`、`section_titles`、`text`，而不是依赖旧字段名。
- 要求 `search` 在命中子节点时支持基于 `parent_id` 回收父节点正文，作为可选父级上下文返回，而不是依赖 payload 内嵌的 `parent_content`。
- 更新 smoke / 测试 / 调试输出约定，使人工验证时能直接看到当前知识库的来源定位字段和章节路径。

## 功能 (Capabilities)

### 新增功能

### 修改功能

- `agent-search-tool`: 将 search 的输入输出契约、命中元数据、父级上下文回收和 smoke 验证方式更新为与当前 RAG 知识库 schema 一致。

## 影响

- 受影响代码：新增 `trpg_py/rag/retriever.py` 承接混合检索、payload 解析与父节点回收；`trpg_py.agent.tools.search` 调整为 tool 包装层；`smoke/test_search.py` 的展示字段；相关测试替身与断言。
- 受影响规范：修改 `specs/agent-search-tool/spec.md`。
- 预期结果：search 可以稳定检索并暴露当前 `trpg_knowledge` 中的真实字段，planner 和开发者能看到与文档一致的规则来源与章节上下文，而不是依赖过时 payload 约定。
