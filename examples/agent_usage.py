"""
DMAgent 使用示例
"""
import asyncio
from src.agent.graph import DMAgent, run_agent


async def example_1():
    """示例1: 基本使用"""
    # 创建Agent
    agent = DMAgent(world_state_path="data/world_state.toml")

    # 处理DM输入
    result = await agent.process(
        dm_input="圣武士艾尔德拉使用长剑攻击地精",
        thread_id="combat_session_1"
    )

    # 查看结果
    print("=" * 50)
    print("处理结果:")
    for msg in result["messages"]:
        if hasattr(msg, 'content'):
            print(f"\n{msg.content}")

    # 查看世界状态更新
    print("\n" + "=" * 50)
    print(f"任务队列剩余: {len(result['task_queue'])}")
    print(f"状态更新记录: {len(result['state_updates'])}")


async def example_2():
    """示例2: 使用快捷函数"""
    output = await run_agent(
        dm_input="圣武士对地精释放雷鸣斩",
        world_state_path="data/world_state.toml"
    )
    print(output)


async def example_3():
    """示例3: 带审批的连锁反应"""
    agent = DMAgent(world_state_path="data/world_state.toml")

    # 第一次处理（可能导致连锁反应）
    result = await agent.process(
        dm_input="圣武士用神圣打击击败地精",
        thread_id="session_1"
    )

    # 检查是否有待审批任务
    if result.get("pending_approval"):
        pending = result["pending_approval"]
        print(f"检测到连锁任务: {pending.description}")

        # 用户审批
        user_input = input("是否批准执行此连锁任务? (y/n): ")
        agent.approve_chain(approved=user_input.lower() == 'y')

        # 继续处理（需要重新调用process或使用stream）
        # ...


async def example_4():
    """示例4: 直接使用工具箱"""
    agent = DMAgent(world_state_path="data/world_state.toml")
    toolkit = agent.get_toolkit()

    # 查看当前世界状态schema
    schema = toolkit.state_manager.get_schema()
    print("世界状态结构:", schema)

    # 手动获取状态
    hp = toolkit.state_manager.get("entity.players.player_01.combat.current_hp")
    print(f"玩家当前HP: {hp}")

    # 手动搜索规则
    search_tool = toolkit.get_tools()[0]  # SearchTool
    rules = search_tool._run(query="雷鸣斩 伤害", limit=2)
    print(f"\n雷鸣斩规则:\n{rules}")


async def example_5():
    """示例5: 多轮对话"""
    agent = DMAgent(world_state_path="data/world_state.toml")

    # 第一轮
    result1 = await agent.process("圣武士攻击地精", thread_id="multi_turn")
    print("第一轮完成")

    # 第二轮（继续同一会话）
    result2 = await agent.process("地精反击圣武士", thread_id="multi_turn")
    print("第二轮完成")


if __name__ == "__main__":
    # 运行示例
    print("示例1: 基本使用")
    asyncio.run(example_1())
