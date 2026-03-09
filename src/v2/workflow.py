"""
V2 LangGraph 工作流
"""
import json
from typing import Literal
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .types import AgentState, TaskIntent, LogicResult
from .agents import InterfaceAgent, PathFinder, TaskAgent, ChainAgent
from .executor import LogicRunner, StateWriter


def create_workflow(
    state_manager,
    model: str = "gpt-4o",
    api_key: str | None = None
):
    """创建V2工作流"""
    
    # 初始化组件
    interface_agent = InterfaceAgent(model=model, api_key=api_key)
    path_finder = PathFinder()
    task_agent = TaskAgent(model=model, api_key=api_key)
    logic_runner = LogicRunner(state_manager)
    state_writer = StateWriter(state_manager)
    chain_agent = ChainAgent()
    
    # 定义节点函数
    
    def interface_node(state: AgentState) -> AgentState:
        """InterfaceAgent: 解析用户输入"""
        messages = state["messages"]
        last_message = messages[-1] if messages else None
        
        if isinstance(last_message, HumanMessage):
            user_input = last_message.content
            print(f"\n🎮 DM: {user_input}")
            
            task = interface_agent.parse(user_input)
            print(f"🤖 InterfaceAgent: 识别任务 - {task.description}")
            print(f"   类型: {task.task_type.value}, 行动者: {task.actor}, 目标: {task.target}")
            
            state["current_task"] = task
            state["task_queue"] = state.get("task_queue", []) + [task]
        
        return state
    
    def pathfinder_node(state: AgentState) -> AgentState:
        """PathFinder: 检索相关路径"""
        task = state["current_task"]
        if not task:
            return state
        
        print(f"\n🔍 PathFinder: 检索相关路径...")
        paths = path_finder.find_paths(task)
        state["relevant_paths"] = paths
        
        print(f"   主要路径 ({len(paths.primary_paths)}):")
        for p, t in list(paths.primary_paths.items())[:5]:
            print(f"     - {p}: {t}")
        if len(paths.primary_paths) > 5:
            print(f"     ... 还有 {len(paths.primary_paths) - 5} 条")
        
        return state
    
    def taskagent_node(state: AgentState) -> AgentState:
        """TaskAgent: 生成执行计划"""
        task = state["current_task"]
        paths = state["relevant_paths"]
        
        if not task or not paths:
            return state
        
        print(f"\n📋 TaskAgent: 生成执行计划...")
        plan = task_agent.plan(task, paths)
        state["execution_plan"] = plan
        state["current_step_idx"] = 0
        state["step_results"] = []
        
        print(f"   计划包含 {len(plan.steps)} 个步骤:")
        for step in plan.steps:
            print(f"     [{step.step_id}] {step.description}")
            if step.expression:
                print(f"         表达式: {step.expression}")
        
        return state
    
    def dm_confirm_node(state: AgentState) -> AgentState:
        """DM 确认节点"""
        plan = state.get("execution_plan")
        if not plan:
            return state
        
        print(f"\n" + "="*50)
        print(f"⏸️  DM 确认节点")
        print(f"="*50)
        print(f"任务: {state['current_task'].description}")
        print(f"\n执行计划:")
        for step in plan.steps:
            print(f"  [{step.step_id}] {step.description}")
        
        # 模拟确认（MVP中自动确认）
        # 在实际使用中，这里应该是一个 interrupt 等待用户输入
        print(f"\n✅ 自动确认执行")
        state["confirmation_result"] = True
        
        return state
    
    def execute_step_node(state: AgentState) -> AgentState:
        """执行当前步骤"""
        plan = state.get("execution_plan")
        step_idx = state.get("current_step_idx", 0)
        
        if not plan or step_idx >= len(plan.steps):
            return state
        
        step = plan.steps[step_idx]
        print(f"\n⚡ 执行步骤 [{step.step_id}]: {step.description}")
        
        # 检查条件
        if step.condition and step.condition != "总是":
            # 简化条件判断
            if "命中" in step.condition and step_idx > 0:
                prev_result = state["step_results"][-1] if state["step_results"] else None
                if prev_result and not prev_result.result:
                    print(f"   ⏭️  条件不满足 ({step.condition})，跳过")
                    state["current_step_idx"] = step_idx + 1
                    return state
        
        # 执行表达式
        if step.expression:
            # 构建步骤上下文
            step_context = {}
            for i, r in enumerate(state.get("step_results", [])):
                step_context[f"step_{i+1}"] = r.result
            
            result = logic_runner.evaluate(step.expression, step_context)
            state["step_results"].append(result)
            
            print(f"   🎲 执行: {step.expression}")
            for t in result.trace:
                print(f"      {t}")
            
            # 如果有状态变更，先暂存
            if step.state_changes and result.success:
                pending = state.get("pending_changes", [])
                pending.extend(step.state_changes)
                state["pending_changes"] = pending
        else:
            # 无表达式的步骤（如状态变更）
            if step.state_changes:
                pending = state.get("pending_changes", [])
                pending.extend(step.state_changes)
                state["pending_changes"] = pending
            
            state["step_results"].append(LogicResult(
                success=True, result=None, resolved_paths={}, trace=[]
            ))
        
        state["current_step_idx"] = step_idx + 1
        return state
    
    def statewriter_node(state: AgentState) -> AgentState:
        """StateWriter: 应用状态变更"""
        pending = state.get("pending_changes", [])
        if not pending:
            return state
        
        print(f"\n💾 StateWriter: 应用 {len(pending)} 个状态变更")
        
        # 构建步骤结果映射
        step_results = {}
        for i, r in enumerate(state.get("step_results", [])):
            step_results[f"step_{i+1}"] = r.result
        
        # 应用变更
        changes = state_writer.apply_changes(pending, step_results)
        state["committed_changes"] = state.get("committed_changes", []) + changes
        state["pending_changes"] = []
        
        # 显示变更
        for c in changes:
            print(f"   {c.path}: {c.old_value} → {c.new_value}")
        
        return state
    
    def chainagent_node(state: AgentState) -> AgentState:
        """ChainAgent: 检测连锁反应"""
        changes = state.get("committed_changes", [])
        if not changes:
            return state
        
        print(f"\n🔗 ChainAgent: 检测连锁反应...")
        
        world_state = state["world_state"]
        triggers = chain_agent.check_chains(changes[-5:], world_state)  # 只检查最近的变化
        
        if triggers:
            print(f"   发现 {len(triggers)} 个连锁触发:")
            for t in triggers:
                print(f"     ⚠️  [{t.priority}] {t.condition}")
                print(f"        效果: {t.effect}")
            state["chain_triggers"] = triggers
        else:
            print(f"   无连锁反应")
            state["chain_triggers"] = []
        
        return state
    
    def chain_confirm_node(state: AgentState) -> AgentState:
        """连锁确认节点"""
        triggers = state.get("chain_triggers", [])
        if not triggers:
            return state
        
        print(f"\n" + "="*50)
        print(f"⏸️  连锁确认节点")
        print(f"="*50)
        
        for t in triggers:
            print(f"  {t.condition}")
            print(f"  → {t.effect}")
        
        # MVP中自动确认
        print(f"\n✅ 自动确认连锁")
        
        # 将连锁转换为新任务（简化版）
        for t in triggers:
            if "火药桶" in t.effect and "爆炸" in t.effect:
                # 创建爆炸任务
                chain_task = TaskIntent(
                    task_id=f"chain_{t.priority}",
                    description="火药桶爆炸",
                    task_type=TaskType.INTERACT,
                    actor="火药桶",
                    target="范围内所有生物",
                    action="爆炸",
                    context={"damage": "4d6+2d6", "save_dc": 12}
                )
                state["task_queue"] = state.get("task_queue", []) + [chain_task]
        
        return state
    
    def should_continue(state: AgentState) -> Literal["execute_step", "statewriter", "chain", "next_task", "end"]:
        """决定下一步"""
        plan = state.get("execution_plan")
        step_idx = state.get("current_step_idx", 0)
        
        if plan and step_idx < len(plan.steps):
            return "execute_step"
        
        if state.get("pending_changes"):
            return "statewriter"
        
        if state.get("chain_triggers"):
            return "chain"
        
        if state.get("task_queue"):
            return "next_task"
        
        return "end"
    
    def next_task_node(state: AgentState) -> AgentState:
        """处理下一个任务"""
        queue = state.get("task_queue", [])
        current = state.get("current_task")
        
        # 移除当前任务
        if current and current in queue:
            queue.remove(current)
        
        if queue:
            state["current_task"] = queue[0]
            state["execution_plan"] = None
            state["current_step_idx"] = 0
            state["step_results"] = []
            state["pending_changes"] = []
            state["chain_triggers"] = []
            print(f"\n{'='*50}")
            print(f"📝 新任务: {queue[0].description}")
        else:
            state["current_task"] = None
        
        state["task_queue"] = queue
        return state
    
    # 构建图
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("interface", interface_node)
    workflow.add_node("pathfinder", pathfinder_node)
    workflow.add_node("taskagent", taskagent_node)
    workflow.add_node("dm_confirm", dm_confirm_node)
    workflow.add_node("execute_step", execute_step_node)
    workflow.add_node("statewriter", statewriter_node)
    workflow.add_node("chainagent", chainagent_node)
    workflow.add_node("chain_confirm", chain_confirm_node)
    workflow.add_node("next_task", next_task_node)
    
    # 设置入口
    workflow.set_entry_point("interface")
    
    # 添加边
    workflow.add_edge("interface", "pathfinder")
    workflow.add_edge("pathfinder", "taskagent")
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
        lambda s: "chain_confirm" if s.get("chain_triggers") else "next_task",
        {
            "chain_confirm": "chain_confirm",
            "next_task": "next_task"
        }
    )
    
    workflow.add_edge("chain_confirm", "next_task")
    
    workflow.add_conditional_edges(
        "next_task",
        lambda s: "pathfinder" if s.get("current_task") else "end",
        {
            "pathfinder": "pathfinder",
            "end": END
        }
    )
    
    # 编译
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


from .types import TaskIntent  # 避免循环导入