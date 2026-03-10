"""
V3 工作流测试
测试场景：
1. 艾尔德拉用长剑攻击哥布林
2. 哥布林用弯刀攻击尼古拉斯
3. 艾尔德拉用圣火术点燃炸药桶
"""
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

load_dotenv()

from src.workflow import create_workflow
from src.tools.kv_state import KVStateStore


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def run_scenario(workflow, store, user_input: str, thread_id: str):
    """运行单个测试场景"""
    print_header(f"场景: {user_input}")

    # 重置状态
    store.reload()

    initial_state = {
        "messages": [HumanMessage(content=user_input)],
        "current_task": None,
        "task_queue": [],
        "execution_result": None,
        "pending_changes": [],
        "committed_changes": [],
        "chain_triggers": [],
        "pending_chain_tasks": [],
    }

    config = {"configurable": {"thread_id": thread_id}}

    # 用于去重打印
    printed_task_id = None
    printed_execution_id = None
    printed_chain_id = None

    try:
        print("\n🚀 开始执行...")
        for output in workflow.stream(initial_state, config, stream_mode="values"):
            # 打印当前任务（只在任务变化时打印）
            if output.get("current_task"):
                task = output["current_task"]
                if printed_task_id != id(task):
                    print(f"\n📝 当前任务: {task.description}")
                    print(f"   行动者: {task.actor}, 目标: {task.target}, 动作: {task.action}")
                    printed_task_id = id(task)

            # 打印执行结果（只打印一次）
            if output.get("execution_result"):
                result = output["execution_result"]
                if printed_execution_id != id(result):
                    print(f"\n⚡ 执行结果:")
                    print(f"   {result.narration}")
                    if result.changes:
                        print(f"   状态变更: {len(result.changes)} 项")
                        for c in result.changes:
                            print(f"     [{c.operation}] {c.path}")
                    printed_execution_id = id(result)

            # 打印连锁触发（只打印一次）
            if output.get("chain_triggers"):
                triggers = output["chain_triggers"]
                if printed_chain_id != id(triggers):
                    print(f"\n🔗 连锁触发:")
                    for t in triggers:
                        print(f"   [{t.priority}] {t.condition} -> {t.effect}")
                    printed_chain_id = id(triggers)

            # 打印待审批连锁任务
            if output.get("pending_chain_tasks"):
                print(f"\n⏸️  待审批连锁任务:")
                for task in output["pending_chain_tasks"]:
                    print(f"   - {task.description}")

        print("\n✅ 场景执行完成")

    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    print_header("TRPG V3 工作流测试")

    # 加载世界状态
    print("\n📂 加载世界状态...")
    store = KVStateStore("data/world_state.txt")
    print(f"   加载了 {len(store.get_keys())} 个状态键")

    # 创建工作流
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL")

    if not api_key:
        print("\n⚠️  未配置 DEEPSEEK_API_KEY，将使用 fallback 模式")

    print("\n🔧 创建工作流...")
    workflow, store = create_workflow(
        world_state_path="data/world_state.txt",
        model="deepseek-chat",
        api_key=api_key,
        base_url=base_url
    )
    print("   工作流创建成功")

    # 测试场景
    scenarios = [
        "艾尔德拉用长剑攻击哥布林",
        "哥布林用弯刀攻击尼古拉斯",
        "艾尔德拉用圣火术点燃炸药桶",
    ]

    for i, scenario in enumerate(scenarios, 1):
        run_scenario(workflow, store, scenario, f"scene_{i}")
        if i < len(scenarios):
            print("\n⏎ 继续下一个场景...")

    print_header("测试完成")


if __name__ == "__main__":
    main()
