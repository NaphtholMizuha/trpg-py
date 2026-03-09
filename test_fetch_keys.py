"""
FetchKeys Tool 测试脚本

测试 fetchkeys 工具使用 LLM 分析查询关键词并返回候选路径的功能。
"""

import json
import argparse
import os
from pathlib import Path

from langchain_openai import ChatOpenAI
from src.tools.toolkit import TrpgToolkit


# ============================================
# 测试类
# ============================================

class FetchKeysTester:
    """FetchKeys 工具测试器"""
    
    def __init__(self, world_state_path: str, model: str, api_key: str | None, base_url: str | None):
        """
        初始化测试器
        
        Args:
            world_state_path: 世界状态文件路径
            model: 模型名称
            api_key: API 密钥
            base_url: API 基础地址
        """
        # 加载世界状态
        path = Path(world_state_path)
        if not path.exists():
            raise FileNotFoundError(f"世界状态文件不存在: {world_state_path}")
        
        with open(path, "r", encoding="utf-8") as f:
            self.world_state = json.load(f)
        
        print(f"✓ 已加载世界状态: {world_state_path}")
        
        # 检查 API key
        if not api_key:
            raise ValueError(
                "未提供 API 密钥！\n"
                "请使用 --api-key 参数或设置环境变量:\n"
                "  - OpenAI: OPENAI_API_KEY\n"
                "  - DeepSeek: DEEPSEEK_API_KEY"
            )
        
        # 初始化 LLM
        llm_kwargs = {
            "model": model,
            "api_key": api_key,
            "temperature": 0,
        }
        if base_url:
            llm_kwargs["base_url"] = base_url
        
        self.llm = ChatOpenAI(**llm_kwargs)
        print(f"✓ 已初始化 LLM (模型: {model})")
        
        # 初始化 Toolkit
        self.toolkit = TrpgToolkit(initial_state=self.world_state, llm=self.llm)
        self.fetchkeys = self._get_fetchkeys_tool()
        print()
    
    def _get_fetchkeys_tool(self):
        """获取 fetchkeys 工具实例"""
        for tool in self.toolkit.get_tools():
            if tool.name == "fetchkeys":
                return tool
        raise RuntimeError("未找到 fetchkeys 工具")
    
    def run_test(self, query: str, top_k: int = 3) -> dict:
        """
        运行单个测试用例
        
        Args:
            query: 查询关键词
            top_k: 返回候选数量
            
        Returns:
            解析后的结果字典
        """
        print(f"🔍 查询: {query}")
        print("-" * 50)
        
        result_str = self.fetchkeys._run(keys=query, top_k=top_k)
        result = json.loads(result_str)
        
        # 显示结果
        if "error" in result:
            print(f"❌ 错误: {result['error']}")
        else:
            print(f"✓ 找到 {len(result['candidates'])} 个候选路径:")
            for i, cand in enumerate(result['candidates'], 1):
                print(f"  {i}. {cand['path']}")
                print(f"     值: {cand['value_preview']}")
        
        # 显示 LLM 推理过程（截断）
        if "llm_reasoning" in result:
            reasoning = result['llm_reasoning'].strip()
            if reasoning:
                preview = reasoning[:200] + "..." if len(reasoning) > 200 else reasoning
                print(f"\n📝 LLM 推理:\n{preview}")
        
        print()
        return result
    
    def run_all_tests(self, test_cases: list[str] = None):
        """
        运行所有测试用例
        
        Args:
            test_cases: 自定义测试用例列表，默认使用预设用例
        """
        if test_cases is None:
            test_cases = [
                # 基础查询
                "艾尔德拉 hp",
                "艾尔德拉 AC",
                "艾尔德拉 力量",
                "艾尔德拉 法术位",
                
                # 敌人查询
                "地精 生命值",
                "地精 AC",
                
                # 物品查询
                "火药桶 状态",
                "火药桶 伤害",
                
                # 混合中英文
                "艾尔德拉 current_hp",
                "goblin hp",
                
                # 复杂查询（需要 LLM 语义理解）
                "艾尔德拉还剩多少血",
            ]
        
        print("=" * 60)
        print("FetchKeys Tool 测试开始")
        print("=" * 60)
        print()
        
        results = []
        for query in test_cases:
            try:
                result = self.run_test(query, top_k=3)
                results.append((query, True, result))
            except Exception as e:
                print(f"❌ 测试失败: {e}\n")
                results.append((query, False, None))
        
        # 汇总
        print("=" * 60)
        print("测试结果汇总")
        print("=" * 60)
        
        success_count = sum(1 for _, ok, _ in results if ok)
        total_count = len(results)
        
        for query, ok, result in results:
            icon = "✅" if ok else "❌"
            print(f"{icon} {query}")
        
        print(f"\n总计: {success_count}/{total_count} 通过")
        
        return results


# ============================================
# 主程序
# ============================================

def main():
    parser = argparse.ArgumentParser(description="FetchKeys Tool 测试")
    parser.add_argument("--state", type=str, default="data/world_state.json",
                        help="世界状态文件路径")
    parser.add_argument("--model", type=str, default="gpt-4o",
                        help="模型名称")
    parser.add_argument("--api-key", type=str, default=None,
                        help="API 密钥")
    parser.add_argument("--base-url", type=str, default=None,
                        help="API 基础地址")
    parser.add_argument("--deepseek", action="store_true",
                        help="使用 DeepSeek API")
    parser.add_argument("--query", type=str, default=None,
                        help="运行单个查询测试")
    
    args = parser.parse_args()
    
    # 处理配置（与 test.py 相同逻辑）
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
    
    try:
        # 初始化测试器
        tester = FetchKeysTester(
            world_state_path=args.state,
            model=model,
            api_key=api_key,
            base_url=base_url
        )
        
        # 运行测试
        if args.query:
            # 单个查询模式
            tester.run_test(args.query, top_k=3)
        else:
            # 完整测试模式
            tester.run_all_tests()
            
    except ValueError as e:
        print(f"❌ 初始化失败: {e}")
        return 1
    except Exception as e:
        print(f"❌ 运行错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
