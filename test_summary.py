"""
测试分层摘要功能
"""
import json
from src.tools.state import StateManager
from src.v2.utils.state_summary import StateSummarizer, format_state_for_llm


def load_world_state(path: str = "data/world_state.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    print("=" * 60)
    print("📝 状态分层摘要示例")
    print("=" * 60)
    
    # 加载状态
    world_data = load_world_state()
    state_manager = StateManager(world_data)
    
    summarizer = StateSummarizer(state_manager)
    
    # 示例1: 完整摘要
    print("\n【完整状态摘要】")
    print("-" * 60)
    summary = summarizer.summarize_all()
    print(summary)
    
    # 示例2: 特定实体摘要
    print("\n\n【特定实体摘要 - 艾尔德拉】")
    print("-" * 60)
    entity_summary = summarizer.summarize_entity("艾尔德拉")
    print(entity_summary)
    
    # 示例3: 关注特定实体（用于LLM）
    print("\n\n【LLM关注模式 - 艾尔德拉 + 地精掠夺者】")
    print("-" * 60)
    llm_summary = format_state_for_llm(state_manager, focus_entities=["艾尔德拉", "地精"])
    print(llm_summary)
    
    print("\n" + "=" * 60)
    print("✅ 摘要示例完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
