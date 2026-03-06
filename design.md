# 节点梗概

- 意图分析：用LLM将DM的描述转述为相对结构化的任务，并将其入队
- 规则获取：当队列非空时从队列中取出任务，FetchSchemaTool查询世界状态长什么样子，用BatchGetTool获取感兴趣的值，用LLM构造RAG prompt，调用SearchTool查找这个任务需要查阅的规则，返回
- 逻辑判定：用LLM根据任务描述和规则上下文，调用，构造出表达式，并调用EvaluateMechanicsTool运行表达式,返回表达式及其结果
- 状态更新：用LLM解析表达式结果，使用BatchPatchTool更新世界状态(包括logs)
- 连锁检测：查看状态更新列表，用LLM思考会带来什么新的影响，并建模为结构化任务入队，但是这里的入队需要DM人工审批
- 队列：如果空了就结束。

# 注意事项
- LLM调用tool都是通过toolkit.py导出的工具调用！