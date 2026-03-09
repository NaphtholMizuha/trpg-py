"""
V2 MVP 测试 - 三个战斗场景

测试场景：
1. 艾尔德拉砍地精掠夺者
2. 地精掠夺者用弯刀砍艾尔德拉  
3. 艾尔德拉用圣火术点燃火药桶
"""
import json
import os
from pathlib import Path

from langchain_core.messages import HumanMessage
from src.workflow.graph import create_workflow
from src.types import AgentState
from src.tools.state import StateManager


def load_world_state(path: str = "data/world_state.json") -> dict:
    """加载世界状态"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def print_state_summary(state: AgentState):
    """打印状态摘要"""
    print("\n" + "="*50)
    print("📊 当前状态摘要")
    print("="*50)
    
    world = state.get("world_state", {})
    
    # 玩家状态
    player = world.get("entity", {}).get("players", {}).get("player_01", {})
    combat = player.get("combat", {})
    print(f"\n👤 艾尔德拉")
    print(f"   HP: {combat.get('current_hp', 'N/A')} / {combat.get('max_hp', 'N/A')}")
    print(f"   AC: {combat.get('armor_class', 'N/A')}")
    
    # 敌人状态
    enemy = world.get("entity", {}).get("enemies", {}).get("goblin_01", {})
    print(f"\n👹 {enemy.get('name', '地精')}")
    print(f"   HP: {enemy.get('current_hp', 'N/A')} / {enemy.get('max_hp', 'N/A')}")
    print(f"   AC: {enemy.get('ac', 'N/A')}")
    
    # 火药桶状态
    barrel = world.get("entity", {}).get("objects", {}).get("explosive_barrel", {})
    print(f"\n🛢️ 火药桶")
    print(f"   状态: {barrel.get('state', 'N/A')}")
    
    print("\n" + "="*50)


def run_test_scenario():
    """运行测试场景"""
    
    print("\n" + "🎲" * 25)
    print("🎮 TRPG Agent V2 - MVP 测试")
    print("🎲" * 25)
    
    # 加载世界状态
    print("\n📂 加载世界状态...")
    world_data = load_world_state()
    
    # 初始化状态管理器
    state_manager = StateManager(world_data)
    
    # 创建初始快照用于回滚
    initial_snapshot = state_manager.snapshot()
    
    # 创建工作流
    print("🔧 初始化 V2 Agent 工作流...")
    
    # 获取DeepSeek API配置
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ 请设置 DEEPSEEK_API_KEY 环境变量")
        return
    
    model = "deepseek-chat"
    base_url = "https://api.deepseek.com"
    
    print(f"🔧 使用模型: {model}")
    workflow, state_manager = create_workflow(
        initial_state=world_data,
        model=model,
        api_key=api_key,
        base_url=base_url
    )
    
    # 定义测试场景
    test_scenes = [
        {
            "name": "场景1: 艾尔德拉攻击地精掠夺者",
            "input": "艾尔德拉用长剑攻击地精掠夺者"
        },
        {
            "name": "场景2: 地精掠夺者反击艾尔德拉",
            "input": "地精掠夺者用弯刀攻击艾尔德拉"
        },
        {
            "name": "场景3: 艾尔德拉用圣火术点燃火药桶",
            "input": "艾尔德拉用圣火术点燃火药桶"
        }
    ]
    
    # 运行每个场景
    for i, scene in enumerate(test_scenes, 1):
        print("\n" + "🎲" * 25)
        print(f"🎬 {scene['name']}")
        print("🎲" * 25)
        
        # 初始化状态
        initial_state: AgentState = {
            "messages": [HumanMessage(content=scene["input"])],
            "current_task": None,
            "task_queue": [],
            "state_summary": None,
            "relevant_paths": None,
            "execution_plan": None,
            "current_step_idx": 0,
            "step_results": [],
            "pending_changes": [],
            "committed_changes": [],
            "chain_triggers": [],
            "pending_confirmation": None,
            "confirmation_result": None,
            "world_state": state_manager.snapshot()
        }
        
        # 执行工作流
        config = {"configurable": {"thread_id": f"scene_{i}"}}
        
        try:
            for output in workflow.stream(initial_state, config, stream_mode="values"):
                # 更新世界状态
                state_manager._state = output.get("world_state", state_manager._state)
            
            # 打印最终状态
            final_state = state_manager.snapshot()
            temp_state = {
                "world_state": final_state,
                "committed_changes": output.get("committed_changes", [])
            }
            print_state_summary(temp_state)
            
            # 显示变更历史
            changes = output.get("committed_changes", [])
            if changes:
                print(f"\n📜 本场景变更记录:")
                for c in changes[-3:]:  # 只显示最近3条
                    print(f"   {c.path}: {c.old_value} → {c.new_value}")
            
        except Exception as e:
            print(f"❌ 场景执行失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "🎲" * 25)
    print("✅ 所有场景测试完成")
    print("🎲" * 25)
    
    # 最终状态
    print_state_summary({"world_state": state_manager.snapshot()})


if __name__ == "__main__":
    run_test_scenario()
