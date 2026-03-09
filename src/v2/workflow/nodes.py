"""
工作流节点函数
"""
from langchain_core.messages import HumanMessage

from ..core.agent_state import AgentState
from ..core.task_intent import TaskIntent
from ..core.execution import ExecutionPlan
from ..core.logic_result import LogicResult
from ..core.chain_trigger import ChainTrigger


def create_interface_node(interface_agent):
    """创建InterfaceAgent节点"""
    def interface_node(state: AgentState) -> AgentState:
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
    return interface_node


def create_summarizer_node(state_manager):
    """创建状态摘要节点（直接列出相关叶子节点）"""
    def summarizer_node(state: AgentState) -> AgentState:
        task = state["current_task"]
        if not task:
            return state
        
        print(f"\n📝 状态摘要: 提取相关实体属性...")
        
        # 获取所有叶子路径
        all_paths = state_manager.get_all_leaf_paths()
        
        # 提取任务中提到的实体关键词
        keywords = []
        if task.actor:
            keywords.append(task.actor.lower())
        if task.target:
            keywords.append(str(task.target).lower())
        
        # 过滤相关路径（匹配实体名称）
        relevant_paths = []
        for path, value in all_paths:
            path_lower = path.lower()
            # 检查是否匹配任何关键词
            if any(kw in path_lower or path_lower.find(kw.replace(' ', '_')) >= 0 for kw in keywords):
                # 格式化显示：路径 = 值（截断）
                value_str = str(value)
                if len(value_str) > 30:
                    value_str = value_str[:27] + "..."
                relevant_paths.append(f"  {path} = {value_str}")
        
        # 如果没有匹配到，显示所有路径
        if not relevant_paths:
            relevant_paths = [f"  {path} = {str(value)[:30]}" for path, value in all_paths[:20]]
        
        summary = "\n".join(relevant_paths)
        state["state_summary"] = summary
        
        print(f"\n{summary}\n")
        
        return state
    return summarizer_node


def create_ragagent_node(rag_agent):
    """创建RagAgent节点"""
    def ragagent_node(state: AgentState) -> AgentState:
        task = state["current_task"]
        if not task:
            return state
        
        print(f"\n📚 RagAgent: 检索D&D 5e规则...")
        
        rules = rag_agent.retrieve(task)
        state["retrieved_rules"] = rules
        
        return state
    return ragagent_node


def create_taskagent_node(task_agent):
    """创建TaskAgent节点"""
    def taskagent_node(state: AgentState) -> AgentState:
        task = state["current_task"]
        state_summary = state.get("state_summary", "")
        rules = state.get("retrieved_rules", "")
        
        if not task:
            return state
        
        print(f"\n📋 TaskAgent: 生成执行计划...")
        plan = task_agent.plan(task, state_summary, rules)
        state["execution_plan"] = plan
        state["current_step_idx"] = 0
        state["step_results"] = []
        
        print(f"   计划包含 {len(plan.steps)} 个步骤:")
        for step in plan.steps:
            print(f"     [{step.step_id}] {step.description}")
            if step.expression:
                print(f"         表达式: {step.expression}")
        
        return state
    return taskagent_node


def dm_confirm_node(state: AgentState) -> AgentState:
    """DM确认节点"""
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
    
    print(f"\n✅ 自动确认执行")
    state["confirmation_result"] = True
    
    return state


def create_execute_step_node(logic_runner, narrator_agent=None):
    """创建执行步骤节点"""
    def execute_step_node(state: AgentState) -> AgentState:
        plan = state.get("execution_plan")
        step_idx = state.get("current_step_idx", 0)
        
        if not plan or step_idx >= len(plan.steps):
            return state
        
        step = plan.steps[step_idx]
        print(f"\n⚡ 执行步骤 [{step.step_id}]: {step.description}")
        
        # 检查条件
        if step.condition and step.condition != "总是":
            if "命中" in step.condition and step_idx > 0:
                # 前一步是攻击检定+命中判定，结果是布尔值
                prev_result = state["step_results"][-1] if state["step_results"] else None
                if prev_result and prev_result.result is False:
                    print(f"   ⏭️  条件不满足 ({step.condition}，攻击未命中)，跳过")
                    state["current_step_idx"] = step_idx + 1
                    return state
                elif prev_result and prev_result.result is True:
                    print(f"   ✅ 条件满足 ({step.condition}，攻击命中)，继续执行")
        
        # 执行表达式
        if step.expression:
            step_context = {}
            for i, r in enumerate(state.get("step_results", [])):
                step_context[f"step_{i+1}"] = r.result
            
            result = logic_runner.evaluate(step.expression, step_context)
            state["step_results"].append(result)
            
            # 生成解说
            if narrator_agent:
                narration = narrator_agent.narrate(step, result, {})
                print(f"   📜 {narration}")
            else:
                print(f"   🎲 执行: {step.expression}")
                for t in result.trace:
                    print(f"      {t}")
            
            if step.state_changes and result.success:
                pending = state.get("pending_changes", [])
                pending.extend(step.state_changes)
                state["pending_changes"] = pending
        else:
            if step.state_changes:
                pending = state.get("pending_changes", [])
                pending.extend(step.state_changes)
                state["pending_changes"] = pending
            
            state["step_results"].append(LogicResult(
                success=True, result=None, resolved_paths={}, trace=[]
            ))
        
        state["current_step_idx"] = step_idx + 1
        return state
    return execute_step_node


def create_statewriter_node(state_writer):
    """创建StateWriter节点"""
    def statewriter_node(state: AgentState) -> AgentState:
        pending = state.get("pending_changes", [])
        if not pending:
            return state
        
        print(f"\n💾 StateWriter: 应用 {len(pending)} 个状态变更")
        
        step_results = {}
        for i, r in enumerate(state.get("step_results", [])):
            step_results[f"step_{i+1}"] = r.result
        
        changes = state_writer.apply_changes(pending, step_results)
        state["committed_changes"] = state.get("committed_changes", []) + changes
        state["pending_changes"] = []
        
        for c in changes:
            print(f"   {c.path}: {c.old_value} → {c.new_value}")
        
        return state
    return statewriter_node


def create_chainagent_node(chain_agent):
    """创建ChainAgent节点"""
    def chainagent_node(state: AgentState) -> AgentState:
        changes = state.get("committed_changes", [])
        if not changes:
            return state
        
        print(f"\n🔗 ChainAgent: 检测连锁反应...")
        
        world_state = state["world_state"]
        triggers = chain_agent.check_chains(changes[-5:], world_state)
        
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
    return chainagent_node


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
    
    print(f"\n✅ 自动确认连锁")
    
    # 将连锁转换为新任务
    for t in triggers:
        if "火药桶" in t.effect and "爆炸" in t.effect:
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


def next_task_node(state: AgentState) -> AgentState:
    """处理下一个任务"""
    from ..core.enums import TaskType
    
    queue = state.get("task_queue", [])
    current = state.get("current_task")
    
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


def should_continue(state: AgentState):
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


def should_continue_chain(state: AgentState):
    """决定连锁后下一步"""
    return "chain_confirm" if state.get("chain_triggers") else "next_task"


def should_continue_next_task(state: AgentState):
    """决定是否继续下一个任务"""
    return "summarizer" if state.get("current_task") else "end"
