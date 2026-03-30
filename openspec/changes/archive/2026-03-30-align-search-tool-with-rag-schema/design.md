## 上下文

`doc/rag.md` 已经把当前规则知识库的检索事实描述清楚了：

- Qdrant 集合固定为 `trpg_knowledge`
- 每个 point 同时带 `dense` 和 `sparse` 两种向量
- payload 收敛为 `book`、`path`、`doc_type`、`title`、`parent_id`、`section_titles`、`text`
- 节点按父子结构组织，命中子节点后应能沿 `parent_id` 回收更完整的上下文

但当前 `trpg_py.agent.tools.search` 仍保留旧假设：

- `_extract_text()` 优先取 `content`
- `_point_to_hit()` 依赖 `parent_content`
- smoke 展示字段仍偏向 `file`、`locator`、`type`

这意味着 search 虽然已经具备混合召回和 rerank 的骨架，但尚未与当前知识库 schema 对齐，导致工具返回体和人工验证输出都不能稳定反映真实入库结构。

## 目标 / 非目标

**目标：**

- 让 search 的 payload 解析与返回契约对齐 `rag.md` 中的当前知识库 schema。
- 让 search 在命中子节点时，能够基于 `parent_id` 回收父节点正文，向调用方暴露更完整的上下文。
- 保持现有 `status=ok/no_match/error` 语义和混合检索 + rerank 主链路不变，只调整命中映射层。
- 更新 smoke 与测试，使开发者可以直接观察 `book/path/doc_type/section_titles` 这类当前真实字段。

**非目标：**

- 不修改知识入库流程或 `rag.md` 中定义的 payload schema。
- 不替换现有 dense / sparse / reranker 提供方，也不改变混合检索策略。
- 不让 search 直接做规则总结、事实抽取或 planner 决策。
- 不在本次变更中扩展多集合搜索或新增过滤语法。

## 决策

### 决策 1：将检索编排与 Tool 包装拆层，Retriever 落在 `trpg_py.rag.retriever`

当前 `trpg_py.agent.tools.search` 把底层检索、rerank、payload 适配、父节点回收、结构化结果和 LangChain tool 包装放在同一模块里，后续继续演进两段式父子节点检索时会让 agent 接口和检索基础设施继续耦合。

因此本次实现应明确拆成两层：

- `trpg_py.rag.retriever` 中提供面向 RAG 的 `Retriever`，负责混合召回、两段式 rerank/父节点回收编排，以及当前知识库 schema 的 payload 规范化。
- `trpg_py.agent.tools.search` 中保留 `SearchTool` 和默认构造入口，负责参数校验、日志记录，以及把 `Retriever` 的结果暴露给 agent/tool 调用方。

这样可以让未来的 smoke、脚本、非 agent 调用方和其他检索能力复用同一个 `Retriever`，而不会依赖 LangChain tool 包装层。

考虑过的替代方案：

- 保持全部逻辑留在 `agent.tools.search`：拒绝。会让 RAG 基础设施继续依附在 agent 包内，难以复用和测试。
- 只拆出底层 Qdrant client，不拆两段式编排：拒绝。真正容易膨胀的是检索编排和 schema 适配逻辑，而不只是客户端创建。

### 决策 2：在 Retriever 内增加显式的 payload 规范化层

search 的核心问题不是召回链路，而是“如何把当前 payload 稳定映射成工具返回体”。因此需要在 Retriever 内显式收敛一层 schema 适配：

- 以 `payload.text` 作为规则正文的 canonical 来源。
- 为兼容已有测试替身和过渡数据，允许短期回退到 `content`，但新契约只承诺 `text`。
- `metadata` 仅稳定暴露 `book`、`path`、`doc_type`、`title`、`parent_id`、`section_titles` 以及内部补充的 `point_id`。
- 不再把 `file`、`type`、`parent_content` 视为长期契约字段。

这样可以把“Qdrant 里可能出现的历史字段”与“search 向外承诺的字段”分开，避免调用方继续绑定旧 schema。

考虑过的替代方案：

- 直接在现有 `_extract_text()` / `_point_to_hit()` 上零散改字段名：拒绝。容易再次把过渡兼容逻辑和长期契约混在一起。
- 让 smoke 脚本自行适配多个字段名：拒绝。会让工具和调试视图继续分裂。

### 决策 3：采用“两段式”排序与上下文回收，先 rerank 子块，再补父块

`rag.md` 明确父子节点关系通过 `parent_id` 表达，但这不意味着应在 rerank 前就把完整父块注入每个候选。search 应采用两段式流程：

- 混合召回后的 reranker 仍以子节点为主排序单元，输入以 `title`、`section_titles` 和子节点 `text` 为主。
- 父节点正文只在最终返回的 hits 中按 `parent_id` 尝试回收，不参与召回候选阶段的主排序。
- 对重复 `parent_id` 做去重，避免对同一个父节点重复查询。
- 父节点查回成功时，将其正文填入 `parent_text`。
- 若 `parent_id` 缺失、父节点不存在或查询失败，search 仍保持当前命中结果有效，只是不返回 `parent_text`。

这样既保留“命中细粒度子块后补回大段上下文”的能力，也避免父块长文本和重复上下文污染 rerank 排序，同时不会把一次局部父节点读取失败升级成整次 search 错误。

考虑过的替代方案：

- 在 rerank 前为每个候选注入完整父块：拒绝。会稀释子块的细粒度匹配信号，并让共享同一父块的候选在 rerank 时变得过于相似。
- 继续要求 payload 内嵌 `parent_content`：拒绝。与当前最小 payload 目标相冲突。
- 父节点读取失败时把整次 search 置为 `error`：拒绝。会让附加上下文能力反过来拖垮主检索链路。

### 决策 4：保持 `SearchResult` 外层语义稳定，只升级 hit 元数据契约

planner 已依赖 `ok/no_match/error` 分支语义，因此本次不改变 `SearchResult` 顶层结构，而是在 Tool 层继续暴露 `SearchResult` / `SearchHit` 语义，并由底层 Retriever 提供其所需的规范化命中数据：

- `text` 表示命中的节点正文
- `metadata.title`、`metadata.doc_type`、`metadata.book`、`metadata.path`、`metadata.section_titles` 用于来源说明和路径展示
- `metadata.parent_id` 用于显式暴露父子关系
- `parent_text` 表示可选回收的父节点正文

这样调用方不需要为本次对齐改写状态分支判断，但可以开始消费更稳定的来源字段。

考虑过的替代方案：

- 直接重构整个返回体，引入 `source`、`parent` 等新对象层级：暂不采用。会放大对 planner、smoke 和测试的兼容成本。

### 决策 5：smoke 和测试改为围绕当前知识库字段做验证，而不是继续展示旧键名

人工 smoke 的主要价值是“快速判断 search 是否真的在当前知识库上工作”。因此输出应优先展示：

- `title`
- `doc_type`
- `book`
- `path`
- `section_titles`
- 可选的 `parent_text` 预览

对应测试替身也应从 `content/file/locator/type/parent_content` 迁移到以 `text/book/path/doc_type/section_titles/parent_id` 为主，确保回归测试验证的是当前数据契约，而不是历史兼容路径。

考虑过的替代方案：

- 保留旧输出字段，同时额外拼接新字段：拒绝。会削弱“哪些字段才是当前稳定契约”的信号。

## 风险 / 权衡

- [真实数据中的 `parent_id` 格式与 point id 不完全一致] → 先把父节点回收设计成宽松增强能力；若无法命中则返回空 `parent_text`，并在真实 smoke 中验证映射方式。
- [父节点回收带来额外 Qdrant 查询成本] → 仅对最终 hits 回收，且按唯一 `parent_id` 去重，避免在召回候选阶段放大成本。
- [Retriever 和 Tool 的返回边界不清晰] → 让 Retriever 负责候选/命中规范化与父节点回收，`SearchTool` 只负责 `SearchResult` 包装、日志和 invoke 入口。
- [调用方可能仍依赖旧 metadata 键名] → 通过规范、smoke 和测试统一迁移到新字段，同时短期保留正文字段的 `content -> text` 回退兼容。
- [当前测试夹具与真实 schema 偏差较大] → 优先先改测试替身字段，使单元测试直接体现 `rag.md` 所描述的结构。

## Migration Plan

1. 修改 `agent-search-tool` 规范，明确当前 payload 字段、父级上下文回收和 smoke 输出要求。
2. 在 `trpg_py/rag/retriever.py` 中实现 Retriever，并承接当前 schema 的 payload 映射与 `parent_id` 回收逻辑。
3. 将 `trpg_py.agent.tools.search` 调整为复用 Retriever，只保留 Tool 包装与 agent 入口。
4. 更新 `smoke/test_search.py` 和 `tests/test_agent_search.py`，让示例点和断言与当前知识库字段对齐。
5. 用真实集合做一次 smoke，确认 `trpg_knowledge` 中子节点命中时可以看到来源字段，并在存在父节点时补回 `parent_text`。
6. 若真实父节点映射不成立，可先回滚父节点回收实现，仅保留当前 payload 字段对齐；这不会影响主检索链路。

## Open Questions

- `parent_id` 在真实入库数据里是否与 Qdrant point id 完全一致，还是需要一层额外映射？
- `section_titles` 在工具返回中是否保持原始列表即可，还是需要同时提供拼接后的显示字符串？
- 是否需要在后续变更里增加 `doc_type` 过滤等面向知识库结构的检索控制参数？
