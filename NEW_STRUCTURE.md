# 新目录结构

src/
  __init__.py
  
  # 核心类型定义
  types.py          # TaskIntent, ExecutionPlan, AgentState, etc.
  enums.py          # TaskType
  
  # Agent 层
  agents/
    __init__.py
    interface.py    # InterfaceAgent - 解析玩家输入
    rag.py          # RagAgent - 检索规则
    task.py         # TaskAgent - 生成执行计划
    narrator.py     # NarratorAgent - 解说执行结果
    chain.py        # ChainAgent - 检测连锁反应
  
  # 执行层
  executors/
    __init__.py
    logic.py        # LogicRunner - 执行表达式
    state_writer.py # StateWriter - 应用状态变更
  
  # 工具层
  tools/
    __init__.py
    rag.py          # Retriever - RAG检索
    state.py        # StateManager - 状态管理
  
  # 工作流
  workflow/
    __init__.py
    graph.py        # LangGraph组装
    nodes.py        # 节点函数
