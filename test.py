"""
V7 工作流测试 (队列管理 + 事件驱动)

测试场景：
1. 艾尔德拉用长剑攻击哥布林
2. 哥布林用弯刀攻击尼古拉斯
3. 艾尔德拉用圣火术点燃炸药桶

使用方式：
  python test.py                            # 默认使用 deepseek，自动确认模式
  python test.py --manual                   # 手动审批模式
  python test.py --provider minimax         # 使用 minimax-m2.5
  python test.py --provider openai          # 使用 openai

环境变量配置：
  DEEPSEEK_API_KEY      - DeepSeek API 密钥
  DEEPSEEK_BASE_URL     - DeepSeek API 地址（可选）
  MINIMAX_API_KEY       - MiniMax API 密钥
  OPENAI_API_KEY        - OpenAI API 密钥
  OPENAI_BASE_URL       - OpenAI API 地址（可选）
"""
import os
import argparse
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

load_dotenv()

from src.utils.logging import configure_logging
# 配置日志只输出 INFO 及以上级别
configure_logging(debug=True)

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
        "changes": [],
        "task_queue": [],
        "metadata": {},
        "_event": None,
        "_current_task": None,
    }

    config = {"configurable": {"thread_id": thread_id}}

    # 用于去重打印
    printed_task_id = None
    printed_event_type = None

    try:
        print("\n🚀 开始执行...")
        for output in workflow.stream(initial_state, config, stream_mode="values"):
            # 获取当前事件
            event = output.get("_event")
            event_type = type(event).__name__ if event else "None"

            # 打印当前任务（只在任务变化时打印）
            current_task = output.get("_current_task")
            if current_task:
                if printed_task_id != id(current_task):
                    print(f"\n📝 当前任务: {current_task.description}")
                    print(f"   行动者: {current_task.actor}, 目标: {current_task.target}")
                    if current_task.source == "chain":
                        print(f"   来源: 连锁触发")
                    printed_task_id = id(current_task)

            # 打印事件（只在事件类型变化时打印）
            if event and printed_event_type != event_type:
                print(f"\n📡 事件: {event_type}")

                if hasattr(event, 'narration'):
                    print(f"   描述: {event.narration}")

                if hasattr(event, 'changes') and event.changes:
                    print(f"   状态变更: {len(event.changes)} 项")
                    for c in event.changes:
                        print(f"     [{c.operation.value}] {c.path}: {c.old_value} -> {c.new_value}")

                if hasattr(event, 'triggered_chains') and event.triggered_chains:
                    print(f"   连锁触发: {len(event.triggered_chains)} 个")
                    for chain in event.triggered_chains:
                        print(f"     - {chain.get('type', 'unknown')}: {chain.get('description', '')}")

                printed_event_type = event_type

            # 打印队列状态
            queue = output.get("task_queue", [])
            if queue and len(queue) > 0:
                print(f"\n📋 任务队列: {len(queue)} 个待处理")

        print("\n✅ 场景执行完成")

    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="TRPG V7 工作流测试")
    parser.add_argument(
        "--manual",
        action="store_true",
        help="启用手动审批模式（默认自动确认）"
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["deepseek", "minimax", "openai"],
        default="deepseek",
        help="选择LLM提供商（默认: deepseek）"
    )
    args = parser.parse_args()

    # 只有在没有 --manual 参数时才设置自动确认
    if not args.manual:
        os.environ["TRPG_AUTO_CONFIRM"] = "1"
        print("🤖 自动确认模式（使用 --manual 启用手动审批）")
    else:
        print("👤 手动审批模式")

    print_header("TRPG V7 工作流测试 (队列管理 + 事件驱动)")
    print(f"   LLM 提供商: {args.provider}")

    # 根据提供商加载配置
    from src.config import AppConfig
    config = AppConfig.from_provider(args.provider)

    # 加载世界状态
    print("\n📂 加载世界状态...")
    store = KVStateStore("data/world_state.txt")
    print(f"   加载了 {len(store.get_keys())} 个状态键")

    # 检查API配置
    if not config.llm_api_key:
        provider_env = {
            "deepseek": "DEEPSEEK_API_KEY",
            "minimax": "MINIMAX_API_KEY",
            "openai": "OPENAI_API_KEY"
        }
        env_var = provider_env.get(args.provider, "API_KEY")
        print(f"\n⚠️  未配置 {env_var}，将使用 fallback 模式")

    print("\n🔧 创建工作流...")
    workflow, store = create_workflow(
        world_state_path="data/world_state.txt",
        model=config.llm_model,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url
    )
    print(f"   工作流创建成功 (模型: {config.llm_model})")

    # 测试场景
    scenarios = [
        # "艾尔德拉用长剑攻击哥布林",
        # "哥布林用弯刀攻击尼古拉斯",
        "马利克发动一环魔法飞弹，3发全部攻击艾尔德拉",
        # "哥布林用弯刀攻击艾尔德拉",
        
    ]

    for i, scenario in enumerate(scenarios, 1):
        run_scenario(workflow, store, scenario, f"scene_{i}")
        if i < len(scenarios):
            print("\n⏎ 继续下一个场景...")

    print_header("测试完成")


if __name__ == "__main__":
    main()
