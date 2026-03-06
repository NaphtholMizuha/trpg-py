"""
DND DM Agent 测试脚本 - 实时显示节点流转
"""

import asyncio
import json
import os


def load_world_state() -> dict:
    """从 TOML 文件加载世界状态"""
    import tomllib

    toml_path = os.path.join(os.path.dirname(__file__), "data", "world_state.toml")
    with open(toml_path, "rb") as f:
        return tomllib.load(f)


def print_node_state(node_name: str, state: dict, dm_output: str):
    """打印节点状态"""
    print(f"\n{'='*20} [{node_name}] {'='*20}")

    if not state:
        if dm_output:
            print(f"  DM输出: {dm_output}")
        return

    # 当前任务
    current_task = state.get("current_task")
    if current_task:
        if hasattr(current_task, 'description'):
            print(f"  当前任务: {current_task.description} [{current_task.type}]")
        else:
            print(f"  当前任务: {current_task.get('description', 'N/A')} [{current_task.get('type', 'N/A')}]")

    # 任务队列
    task_queue = state.get("task_queue", [])
    if task_queue:
        print(f"  任务队列: {len(task_queue)} 个待处理")
        for t in task_queue[:3]:
            if hasattr(t, 'description'):
                print(f"    - {t.description}")
            else:
                print(f"    - {t.get('description', 'N/A')}")

    # 规则上下文
    rules_context = state.get("rules_context", "")
    if rules_context:
        ctx = rules_context[:150].replace("\n", " ")
        print(f"  规则上下文: {ctx}...")

    # 表达式结果
    expression_results = state.get("expression_results", [])
    if expression_results:
        print("  表达式结果:")
        for expr in expression_results:
            print(f"    - {expr.get('description', 'N/A')}: {expr.get('result', 'N/A')}")

    # 状态更新
    state_updates = state.get("state_updates", [])
    if state_updates:
        print("  状态更新:")
        for update in state_updates:
            if hasattr(update, 'path'):
                print(f"    - {update.path}: {update.old_value} → {update.new_value}")
                print(f"      原因: {update.reason}")
            else:
                print(f"    - {update.get('path', 'N/A')}: {update.get('old_value')} → {update.get('new_value')}")

    # DM输出
    if dm_output:
        print(f"  DM输出: {dm_output}")


async def test_agent(dm_input: str):
    """测试 DM Agent - 实时显示节点流转"""
    from langchain_openai import ChatOpenAI
    from src.agent import DMAgent

    # 检查 API Key
    api_key = os.environ.get("SILICONFLOW_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("请设置 SILICONFLOW_API_KEY 或 OPENAI_API_KEY 环境变量")
        return

    # 加载世界状态
    world_state = load_world_state()

    # 初始化 LLM
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")
    llm = ChatOpenAI(
        model="deepseek-ai/DeepSeek-V3",
        api_key=api_key,  # type: ignore[arg-type]
        base_url=base_url
    )

    # 初始化 Agent
    agent = DMAgent(llm, initial_state=world_state)

    print("=" * 60)
    print("DND DM Agent 测试 - 实时节点流转")
    print("=" * 60)

    # 显示初始世界状态
    print("\n[初始世界状态 - player_01.combat]")
    if "player_01" in world_state:
        combat = world_state["player_01"].get("combat", {})
        print(json.dumps(combat, ensure_ascii=False, indent=2))

    print(f"\n[DM输入]: {dm_input}")
    print("-" * 60)

    # 流式处理 - 实时显示节点状态
    async for node_name, state, dm_output in agent.process_stream(dm_input):
        print_node_state(node_name, state, dm_output)

    print("\n" + "=" * 60)
    print("处理完成")
    print("=" * 60)

    # 显示最终世界状态
    print("\n[最终世界状态 - player_01.combat]")
    final_state = agent.world_state
    if "player_01" in final_state:
        combat = final_state["player_01"].get("combat", {})
        print(json.dumps(combat, ensure_ascii=False, indent=2))


def main():
    """主函数"""
    # DM 输入字符串
    DM_INPUT = "艾尔德拉使用长剑攻击面前的哥布林"

    asyncio.run(test_agent(DM_INPUT))


if __name__ == "__main__":
    main()