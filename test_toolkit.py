import os
import json
from openai import OpenAI
from langchain_core.utils.function_calling import convert_to_openai_tool
from src.tools.toolkit import TrpgToolkit # 你的工具箱文件

# ==========================================
# 1. 配置第三方 API (根据你的供应商修改)
# ==========================================
client = OpenAI(
    api_key="sk-d8279ac9d5094a0fa7610e580889820a",             # 填入你的 Key
    base_url="https://api.deepseek.com/v1" # 填入第三方 API 地址 (如 SiliconFlow, DeepSeek 等)
)
MODEL_NAME = "deepseek-chat"           # 填入模型名称

# ==========================================
# 2. 初始化环境
# ==========================================
initial_world = {
    "entities": {
        "warrior": {"name": "格罗格", "hp": 45, "atk_mod": 4},
        "enemies": {
            "goblin_01": {"name": "地精A", "hp": 15, "ac": 12}
        }
    },
    "logs": []
}

toolkit = TrpgToolkit(initial_world)
langchain_tools = toolkit.get_tools()

# 将 LangChain 工具转换为 OpenAI 兼容的 JSON Schema
openai_tools = [convert_to_openai_tool(t) for t in langchain_tools]

# 定义工具名到函数的映射，方便后面调用
tool_map = {t.name: t for t in langchain_tools}

# ==========================================
# 3. 核心 Agent 循环 (手动处理 Tool Call)
# ==========================================
def run_custom_api_test(prompt):
    print(f"\n🚀 [用户指令]: {prompt}")
    
    messages = [
        {"role": "system", "content": "你是一个 TRPG 结算助手。请利用提供的工具维护状态。所有数值计算必须用 evaluate_mechanics，所有修改必须用 modify_state。在结算战斗时，请直接在 evaluate_mechanics 中混合使用路径和掷骰公式进行布尔判定."},
        {"role": "user", "content": prompt}
    ]

    # 限制最大步数，防止死循环
    for _ in range(6):
        # 1. 发送请求给第三方 API
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=openai_tools,
            tool_choice="auto" # 自动决定是否调用工具
        )
        
        resp_msg = response.choices[0].message
        messages.append(resp_msg) # 把模型的回复存入上下文

        # 2. 检查模型是否想调用工具
        if not resp_msg.tool_calls:
            print(f"\n📝 [Agent 最终回复]:\n{resp_msg.content}")
            break

        # 3. 处理模型发起的每一个工具调用
        for tool_call in resp_msg.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)
            
            print(f"\n🛠️ [调用工具] {func_name} | 参数: {func_args}")
            
            # 从工具映射中找到函数并执行
            if func_name in tool_map:
                target_tool = tool_map[func_name]
                observation = target_tool.invoke(func_args)
                print(f"👁️ [工具返回]: {observation}")
                
                # 4. 将执行结果作为 Tool 消息反馈给模型
                messages.append({
                    "role": "tool",
                    "content": str(observation),
                    "tool_call_id": tool_call.id
                })
            else:
                print(f"❌ 找不到工具: {func_name}")

# ==========================================
# 4. 执行测试用例
# ==========================================

# 场景：复杂的战斗结算
test_input = "战士格罗格攻击了地精A。帮我处理结算和记录结果"

run_custom_api_test(test_input)

# 打印最终状态
print("\n" + "="*50)
print("📊 最终世界快照:")
print(toolkit.state_manager.to_json())