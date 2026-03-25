## 1. 工具骨架

- [x] 1.1 审阅 `multi-prompt` 分支中的 `src/tools/rag.py` 与 `src/tools/toolkit.py`，确认可复用的检索和 LangChain 包装模式
- [x] 1.2 创建 `trpg_py.agent.tools` 包结构，并为搜索工具预留模块入口
- [x] 1.3 定义搜索工具的输入输出模型，包括成功、无命中和错误三类返回形状
- [x] 1.4 确定 Qdrant 客户端与集合配置的注入方式，避免在工具内部硬编码连接细节

## 2. 核心搜索实现

- [x] 2.1 实现核心 `search` 逻辑，使其能够根据 query 调用 Qdrant 执行检索
- [x] 2.2 参考 `multi-prompt` 的检索器分层方式，实现 dense + sparse 的混合召回链路
- [x] 2.3 为混合召回结果接入 reranker，并输出最终重排后的命中顺序
- [x] 2.4 将 Qdrant 响应映射为项目内部的结构化 payload，并保留原文与必要元数据
- [x] 2.5 实现空结果与检索错误的显式区分，确保调用方可稳定识别不同状态

## 3. LangChain 集成

- [x] 3.1 参考 `multi-prompt` 的 `SearchTool` 输入 Schema 与 `BaseTool` 组织方式，为核心 `search` 逻辑提供 LangChain tool 包装
- [x] 3.2 确保 LangChain tool 的输入参数和返回语义与核心搜索接口保持一致

## 4. 验证

- [x] 4.1 为核心搜索实现补充测试，覆盖混合检索成功命中、无命中和 Qdrant 失败场景
- [x] 4.2 为 reranker 集成补充测试，验证最终输出顺序来自重排结果而不是原始召回顺序
- [x] 4.3 为 LangChain tool 包装补充测试，验证其复用核心搜索逻辑而不是复制实现
- [x] 4.4 补充简要使用说明，说明搜索工具的职责边界仅限检索规则原文
