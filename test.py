import json
import time
from pathlib import Path
from src.tools.toolkit import TrpgToolkit
from src.agent.agent import DNDAssistantAgent
from langchain_core.messages import AIMessage, ToolMessage

# ============================================
# 1. 加载世界状态
# ============================================

def load_world_state(file_path: str = "data/world_state.json") -> dict:
    """加载 JSON 世界状态"""
    path = Path(file_path)
    if not path.exists():
        print(f"❌ 文件不存在: {file_path}")
        return {}
    
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================
# 2. 测试用例定义 (三大核心场景)
# ============================================

TEST_CASES = [
    {
        "name": "⚔️ 场景1：物理攻击 (长剑)",
        "input": "艾尔德拉用长剑攻击哥布林。",
        "check": lambda r: "命中" in r or "未命中" in r or "hp" in r.lower()
    },
    {
        "name": "🔮 场景2：法术攻击 (圣火术)",
        "input": "艾尔德拉对哥布林施放圣火术。",
        "check": lambda r: "圣火" in r or "光耀" in r or "d20" in r.lower()
    },
    {
        "name": "🛢️ 场景3：环境互动 (点燃炸药桶)",
        "input": "艾尔德拉用火把点燃火药桶。",
        "check": lambda r: "爆炸" in r or "豁免" in r or "伤害" in r
    },
]


# ============================================
# 3. 测试运行器
# ============================================

class AgentTester:
    def __init__(self, world_state_path: str, model: str = "gpt-4o",
                 api_key: str | None = None, base_url: str | None = None,
                 verbose: bool = False):
        print("=" * 60)
        print("🏰 DND DM 助手测试系统 (核心场景版)")
        print("=" * 60)

        # 加载状态
        self.world_state = load_world_state(world_state_path)
        print(f"✓ 已加载世界状态")

        # 初始化 Toolkit 和 Agent
        print("⏳ 正在初始化 Agent...")
        self.toolkit = TrpgToolkit(initial_state=self.world_state)
        self.verbose = verbose

        # 根据配置创建 Agent
        agent_kwargs = {"model": model}
        if api_key:
            agent_kwargs["api_key"] = api_key
        if base_url:
            agent_kwargs["base_url"] = base_url

        self.agent = DNDAssistantAgent(self.toolkit, **agent_kwargs)
        print(f"✓ Agent 初始化完成 (模型: {model})")
        if verbose:
            print("📋 详细模式已启用，将显示内部流转信息")
        print()

    def run_single_test(self, test_case: dict):
        """运行单个测试用例"""
        name = test_case["name"]
        user_input = test_case["input"]
        checker = test_case.get("check", lambda r: True)

        print(f"\n{'='*60}")
        print(f"🧪 测试: {name}")
        print(f"{'='*60}")
        print(f"📝 输入: {user_input}")
        print("-" * 60)

        # 记录初始状态
        state_before = self.toolkit.state_manager.snapshot()

        # 执行
        start_time = time.time()
        try:
            if self.verbose:
                # 详细模式：显示每一步流转
                response = self._run_verbose(user_input)
            else:
                # 简洁模式
                response = self.agent.invoke(user_input)
            elapsed = time.time() - start_time

            print(f"🤖 最终回答: {response}")
            print(f"⏱️  耗时: {elapsed:.2f}s")

            # 验证
            passed = checker(response)
            result_icon = "✅" if passed else "❌"
            print(f"{result_icon} 结果: {'通过' if passed else '未通过'}")

            # 显示关键状态变更
            state_after = self.toolkit.state_manager.snapshot()
            self._show_key_diff(state_before, state_after)

            return passed

        except Exception as e:
            print(f"❌ 执行出错: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _run_verbose(self, user_input: str) -> str:
        """以详细模式运行，显示内部流转"""
        print("\n🔍 [详细模式] Agent 内部流转:")
        print("-" * 50)

        final_response = ""
        for step, message in self.agent.stream(user_input):
            if isinstance(message, AIMessage):
                if message.tool_calls:
                    # AI 决定调用工具
                    print(f"\n📤 步骤 {step}: AI 决定调用工具")
                    for tc in message.tool_calls:
                        print(f"   工具: {tc['name']}")
                        print(f"   参数: {tc['args']}")
                elif message.content:
                    # AI 直接回复
                    print(f"\n💬 步骤 {step}: AI 回复")
                    print(f"   {message.content[:200]}..." if len(message.content) > 200 else f"   {message.content}")
                    final_response = message.content
                else:
                    print(f"\n🤔 步骤 {step}: AI 思考中...")

            elif isinstance(message, ToolMessage):
                # 工具执行结果
                print(f"\n📥 步骤 {step}: 工具返回结果")
                content = message.content
                print(f"   {content[:300]}..." if len(content) > 300 else f"   {content}")

            else:
                print(f"\n📝 步骤 {step}: {type(message).__name__}")

        print("-" * 50)
        return final_response

    def _show_key_diff(self, before: dict, after: dict):
        """显示关键数据的变化"""
        # 检查哥布林HP
        goblin_before = before.get("entity", {}).get("enemies", {}).get("goblin_01", {}).get("current_hp")
        goblin_after = after.get("entity", {}).get("enemies", {}).get("goblin_01", {}).get("current_hp")
        if goblin_before != goblin_after:
            print(f"🔥 状态变更: 哥布林 HP {goblin_before} → {goblin_after}")

        # 检查玩家HP
        player_before = before.get("entity", {}).get("players", {}).get("player_01", {}).get("combat", {}).get("current_hp")
        player_after = after.get("entity", {}).get("players", {}).get("player_01", {}).get("combat", {}).get("current_hp")
        if player_before != player_after:
            print(f"🔥 状态变更: 艾尔德拉 HP {player_before} → {player_after}")
            
        # 检查炸药桶状态
        barrel_before = before.get("entity", {}).get("objects", {}).get("explosive_barrel", {}).get("state")
        barrel_after = after.get("entity", {}).get("objects", {}).get("explosive_barrel", {}).get("state")
        if barrel_before != barrel_after:
            print(f"🔥 状态变更: 炸药桶状态 {barrel_before} → {barrel_after}")

    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "🚀 开始测试".center(60, "="))
        
        results = []
        for test_case in TEST_CASES:
            passed = self.run_single_test(test_case)
            results.append((test_case["name"], passed))
            time.sleep(1)  # 防止 API 限流
        
        # 汇总
        print("\n" + "=" * 60)
        print("📊 测试汇总")
        print("=" * 60)
        
        for name, passed in results:
            icon = "✅" if passed else "❌"
            print(f"{icon} {name}")
        
        total = len(results)
        success = sum(1 for _, p in results if p)
        print(f"\n总计: {success}/{total} 通过")


# ============================================
# 4. 主程序
# ============================================

if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="DND DM Agent 核心测试")
    parser.add_argument("--state", type=str, default="data/world_state.json", help="世界状态文件路径")
    parser.add_argument("--model", type=str, default="gpt-4o", help="模型名称")
    parser.add_argument("--api-key", type=str, default=None, help="API 密钥")
    parser.add_argument("--base-url", type=str, default=None, help="API 基础地址")
    parser.add_argument("--deepseek", action="store_true", help="使用 DeepSeek API")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细内部流转信息")

    args = parser.parse_args()

    # 处理配置
    model = args.model
    base_url = args.base_url
    api_key = args.api_key

    if args.deepseek:
        model = "deepseek-chat"
        base_url = "https://api.deepseek.com"
        if not api_key:
            api_key = os.environ.get("DEEPSEEK_API_KEY")

    if not api_key:
        if "deepseek" in model.lower():
            api_key = os.environ.get("DEEPSEEK_API_KEY")
        else:
            api_key = os.environ.get("OPENAI_API_KEY")

    # 初始化并运行
    tester = AgentTester(
        args.state,
        model=model,
        api_key=api_key,
        base_url=base_url,
        verbose=args.verbose
    )
    tester.run_all_tests()
