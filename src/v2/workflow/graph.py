"""
LangGraph工作流组装
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..core.agent_state import AgentState
from ..agents.interface_agent import InterfaceAgent
from ..agents.rag_agent import RagAgent
from ..agents.task_agent import TaskAgent
from ..agents.narrator_agent import NarratorAgent
from ..agents.chain_agent import ChainAgent
from ..executors.logic_runner import LogicRunner
from ..executors.state_writer import StateWriter
from ...tools.rag import Retriever

from .nodes import (
    create_interface_node,
    create_summarizer_node,
    create_ragagent_node,
    create_taskagent_node,
    dm_confirm_node,
    create_execute_step_node,
    create_statewriter_node,
    create_chainagent_node,
    chain_confirm_node,
    next_task_node,
    should_continue,
    should_continue_chain,
    should_continue_next_task,
)


def create_workflow(state_manager, model: str = "gpt-4o", api_key: str | None = None, base_url: str | None = None):
    """创建V2工作流"""
    
    # 初始化组件
    interface_agent = InterfaceAgent(model=model, api_key=api_key, base_url=base_url)
    # 初始化RAG检索器
    retriever = Retriever()
    rag_agent = RagAgent(model=model, api_key=api_key, base_url=base_url, retriever=retriever)
    task_agent = TaskAgent(model=model, api_key=api_key, base_url=base_url)
    narrator_agent = NarratorAgent(model=model, api_key=api_key, base_url=base_url)
    logic_runner = LogicRunner(state_manager)
    state_writer = StateWriter(state_manager)
    chain_agent = ChainAgent()
    
    # 创建工作流
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("interface", create_interface_node(interface_agent))
    workflow.add_node("summarizer", create_summarizer_node(state_manager))
    workflow.add_node("rag_agent", create_ragagent_node(rag_agent))
    workflow.add_node("taskagent", create_taskagent_node(task_agent))
    workflow.add_node("dm_confirm", dm_confirm_node)
    workflow.add_node("execute_step", create_execute_step_node(logic_runner, narrator_agent))
    workflow.add_node("statewriter", create_statewriter_node(state_writer))
    workflow.add_node("chainagent", create_chainagent_node(chain_agent))
    workflow.add_node("chain_confirm", chain_confirm_node)
    workflow.add_node("next_task", next_task_node)
    
    # 设置入口
    workflow.set_entry_point("interface")
    
    # 添加边
    workflow.add_edge("interface", "summarizer")
    workflow.add_edge("summarizer", "rag_agent")
    workflow.add_edge("rag_agent", "taskagent")
    workflow.add_edge("taskagent", "dm_confirm")
    workflow.add_edge("dm_confirm", "execute_step")
    
    # 条件边
    workflow.add_conditional_edges(
        "execute_step",
        should_continue,
        {
            "execute_step": "execute_step",
            "statewriter": "statewriter",
            "chain": "chainagent",
            "next_task": "next_task",
            "end": END
        }
    )
    
    workflow.add_edge("statewriter", "chainagent")
    
    workflow.add_conditional_edges(
        "chainagent",
        should_continue_chain,
        {
            "chain_confirm": "chain_confirm",
            "next_task": "next_task"
        }
    )
    
    workflow.add_edge("chain_confirm", "next_task")
    
    workflow.add_conditional_edges(
        "next_task",
        should_continue_next_task,
        {
            "summarizer": "summarizer",
            "end": END
        }
    )
    
    # 编译
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
