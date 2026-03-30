## 1. Search Payload 对齐

- [x] 1.1 在 `trpg_py/rag/retriever.py` 中实现 Retriever，并收敛当前知识库 payload 映射，改为以 `text` 作为命中正文来源，并稳定输出 `book`、`path`、`doc_type`、`title`、`parent_id`、`section_titles`
- [x] 1.2 清理 search/Retriever 对 `content`、`file`、`type`、`parent_content` 等旧键名的长期依赖，仅保留必要的过渡兼容逻辑

## 2. Tool 与 Retriever 解耦

- [x] 2.1 将 `trpg_py.agent.tools.search` 调整为复用 `trpg_py.rag.retriever`，使 Tool 只负责参数校验、日志记录和 `SearchResult` 包装
- [x] 2.2 保持现有默认构造入口可用，使 smoke、测试和 planner 调用方无需直接依赖 Qdrant/Reranker 细节

## 3. 父节点上下文回收

- [x] 3.1 将 Retriever 调整为两段式流程：先以子节点正文完成 rerank，再基于 `parent_id` 对最终 hits 做父节点正文回收，并确保查询按唯一 `parent_id` 去重
- [x] 3.2 为父节点缺失、读取失败或 `parent_id` 不可解析的情况补充宽松降级逻辑，保证整次 search 仍返回命中结果而不是 `error`

## 4. 验证与调试输出

- [x] 4.1 更新 `tests/test_agent_search.py` 中的 Qdrant 替身数据和断言，使其覆盖当前 RAG schema 字段、Retriever 分层和父节点回收行为
- [x] 4.2 更新 `smoke/test_search.py` 的人类可读输出，优先展示 `title`、`doc_type`、`book`、`path`、`section_titles` 和可选 `parent_text`
- [x] 4.3 运行相关测试或 smoke 验证 search 输出与 `doc/rag.md` 描述的知识库结构一致
