"""
LangGraph 事件驱动引擎测试
"""
import os
from langchain_openai import ChatOpenAI
from src.agent import TrpgGraph
from src.tools import TrpgToolkit

# ==========================================
# 1. 初始化环境
# ==========================================
initial_world = {
    "entities": {
        "warrior": {"name": "格罗格", "hp": 45, "atk_mod": 4, "ac": 16},
        "goblin": {"name": "地精", "hp": 15, "ac": 12}
    },
    "logs": []
}

toolkit = TrpgToolkit(initial_world)

# 配置 LLM (使用 DeepSeek)
llm = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com/v1",
    api_key=os.environ.get("DEEPSEEK_API_KEY", "sk-d8279ac9d5094a0fa7610e580889820a"),
)

# 创建图实例
graph = TrpgGraph(toolkit, llm)


# ==========================================
# 2. 测试用例
# ==========================================
def test_simple_invoke():
    """测试简单调用"""
    print("\n" + "="*50)
    print("🚀 测试简单调用: 战士攻击地精")
    print("="*50)

    result = graph.invoke("战士格罗格用长剑攻击地精")

    print("\n📊 最终状态:")
    print(toolkit.state_manager.to_json())

    print("\n📝 消息历史:")
    for msg in result.get("messages", []):
        print(f"  - {type(msg).__name__}: {msg.content[:100]}..." if len(str(msg.content)) > 100 else f"  - {type(msg).__name__}: {msg.content}")


def test_stream_invoke():
    """测试流式调用"""
    print("\n" + "="*50)
    print("🚀 测试流式调用")
    print("="*50)

    # 重置状态
    toolkit.state_manager.update(initial_world)

    for step_output in graph.stream("地精用攻击战士"):
        node_name = list(step_output.keys())[0]
        node_output = step_output[node_name]
        print(f"\n📌 节点 [{node_name}]:")
        for key, value in node_output.items():
            if value:
                print(f"  {key}: {str(value)[:100]}..." if len(str(value)) > 100 else f"  {key}: {value}")


def test_heal_scenario():
    """测试治疗场景"""
    print("\n" + "="*50)
    print("🚀 测试治疗场景")
    print("="*50)

    # 设置一个受伤状态
    toolkit.state_manager.set("entities.warrior.hp", 20)

    result = graph.invoke("牧师治疗战士，恢复 1d8+3 点生命值")

    print("\n📊 最终状态:")
    print(toolkit.state_manager.to_json())


if __name__ == "__main__":
    # test_simple_invoke()
    test_stream_invoke()  # 可选：测试流式调用
    test_heal_scenario()  # 可选：测试治疗场景