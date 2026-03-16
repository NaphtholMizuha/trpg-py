"""
Skills系统使用示例

展示如何使用新的Anthropic风格Skills系统进行意图识别和任务规划
"""

from src.skills import get_registry, detect_intent, detect_intent_with_keywords
from src.skills.intent_detector import IntentDetector


def demo_skill_registry():
    """演示Skill注册表功能"""
    print("=" * 60)
    print("Skill 注册表演示")
    print("=" * 60)

    registry = get_registry()
    print(f"\n已加载的Skills: {registry.list_skills()}")

    # 获取单个skill详情
    combat = registry.get_combat_skill()
    if combat:
        print(f"\n[combat]")
        print(f"  描述: {combat.description[:80]}...")
        print(f"  触发关键词: {combat.trigger_keywords[:10]}...")

    world_edit = registry.get_world_edit_skill()
    if world_edit:
        print(f"\n[trpg-world-edit]")
        print(f"  描述: {world_edit.description[:80]}...")
        print(f"  触发关键词: {world_edit.trigger_keywords[:10]}...")


def demo_intent_detection():
    """演示意图识别功能"""
    print("\n" + "=" * 60)
    print("意图识别演示")
    print("=" * 60)

    test_cases = [
        # (输入, 期望意图)
        ("艾尔德拉用长剑攻击地精", "standard"),
        ("艾尔德拉施放火球术", "standard"),
        ("进行敏捷豁免检定", "standard"),
        ("set goblin HP to 0", "world_edit"),
        ("生成一个新的兽人战士", "world_edit"),
        ("heal everyone to full", "world_edit"),
        ("回满血", "world_edit"),
        ("直接杀死这个怪物", "world_edit"),
        ("modify the trap DC to 15", "world_edit"),
        ("add 100 gold to inventory", "world_edit"),
        ("立即删除那个NPC", "world_edit"),
    ]

    print(f"\n{'输入':<40} {'检测意图':<15} {'匹配Skill'}")
    print("-" * 60)

    for user_input, expected in test_cases:
        intent, skill = detect_intent(user_input)
        skill_name = skill.name if skill else "None"
        status = "✓" if intent == expected else "✗"
        print(f"{status} {user_input:<38} {intent:<15} {skill_name}")


def demo_planner_integration():
    """演示与PlannerAgent集成"""
    print("\n" + "=" * 60)
    print("PlannerAgent 集成演示")
    print("=" * 60)

    # 注意：这里只展示集成逻辑，不实际调用LLM
    print("""
使用方式:

    from src.agents import PlannerAgent
    from src.tools import create_tools

    # 创建PlannerAgent（默认启用skills）
    tools = create_tools()
    planner = PlannerAgent(
        model="gpt-4o",
        api_key="your-api-key",
        tools=tools,
        use_skills=True  # 启用意图识别
    )

    # 标准游戏指令 -> 使用combat skill
    task1 = planner.plan("艾尔德拉用长剑攻击地精")
    # intent_type="standard", 使用完整的ReAct流程

    # 世界编辑指令 -> 使用trpg-world-edit skill
    task2 = planner.plan("set goblin HP to 0")
    # intent_type="world_edit", 跳过骰子流程，直接生成变更

意图识别会自动:
1. 根据关键词匹配最合适的skill
2. 动态切换系统提示词
3. 调整任务处理流程
    """)


def demo_llm_intent_detection():
    """演示LLM-based意图识别"""
    print("\n" + "=" * 60)
    print("LLM-based 意图识别演示")
    print("=" * 60)

    print("""
默认使用LLM进行意图识别，出错时自动fallback到关键词匹配：

    from src.skills import detect_intent  # LLM-based
    from src.skills import detect_intent_with_keywords  # 纯关键词

    # 方式1: LLM-based（推荐）
    intent, skill = detect_intent("直接杀死这个怪物")
    # LLM会理解"直接"这个词，识别为world_edit意图

    # 方式2: 自定义IntentDetector（使用特定模型）
    from src.skills.intent_detector import IntentDetector

    detector = IntentDetector(
        model="gpt-4o-mini",
        api_key="your-key",
        base_url="optional-custom-url"
    )
    intent, skill = detector.detect("生成一个新怪物")

特点:
- LLM理解语义，不依赖关键词
- API出错时自动fallback到关键词匹配
- 支持配置不同模型和API端点
""")

    # 实际演示对比
    print("关键词匹配 vs LLM-based（API无效时fallback）:")
    print("-" * 60)

    test_cases = [
        "艾尔德拉攻击地精",
        "set goblin HP to 0",
        "直接满血复活",
        "创建一个隐藏陷阱",
    ]

    for inp in test_cases:
        kw_intent, kw_skill = detect_intent_with_keywords(inp)
        llm_intent, llm_skill = detect_intent(inp)
        kw_name = kw_skill.name if kw_skill else "None"
        llm_name = llm_skill.name if llm_skill else "None"
        match = "✓" if kw_intent == llm_intent else "~"
        print(f"{match} {inp[:30]:<30} | 关键词: {kw_intent:<12} | LLM: {llm_intent}")


def demo_adding_new_skill():
    """演示如何添加新的Skill"""
    print("\n" + "=" * 60)
    print("添加新Skill示例")
    print("=" * 60)

    print("""
添加新Skill的步骤:

1. 在 skills/ 目录下创建新文件夹:
   mkdir skills/my_custom_skill

2. 创建 SKILL.md 文件，遵循Anthropic格式:

   ---
   name: my-custom-skill
   description: 描述这个skill的功能和使用场景
   trigger_keywords:
     - keyword1
     - keyword2
     - 关键词3
   ---

   ## 指令内容

   这里是详细的操作指南...

3. 重启PlannerAgent或重新加载SkillRegistry:

   from src.skills import get_registry
   registry = get_registry()
   registry._load_all_skills()  # 重新加载

4. 新skill会自动参与意图识别

示例：创建一个"骰子历史查询" skill
---
name: dice-history
description: 查询历史骰子记录和统计信息
trigger_keywords:
  - history
  - 历史
  - 统计
  - 之前投了多少
---

当用户说"查看之前的骰子历史"时，会自动匹配到这个skill
    """)


if __name__ == "__main__":
    demo_skill_registry()
    demo_intent_detection()
    demo_llm_intent_detection()
    demo_planner_integration()
    demo_adding_new_skill()

    print("\n" + "=" * 60)
    print("演示完成!")
    print("=" * 60)
