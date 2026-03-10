"""
测试 LogicEngine 修复
"""
import json
from src.tools.logic import LogicEngine
from src.tools.state import StateManager

# 加载世界状态
with open("data/world_state.json", "r", encoding="utf-8") as f:
    world_data = json.load(f)

state_manager = StateManager(world_data)
engine = LogicEngine()

# 测试1: 基本路径访问
print("=" * 50)
print("测试1: 基本路径访问")
print("=" * 50)
state = state_manager.snapshot()
result = engine.eval("entity.players.player_01.combat.current_hp", state)
print(f"表达式: entity.players.player_01.combat.current_hp")
print(f"结果: {result.result}")
print(f"轨迹: {result.resolved}")
print()

# 测试2: 列表索引访问
print("=" * 50)
print("测试2: 列表索引访问")
print("=" * 50)
result = engine.eval("entity.players.player_01.class[0].level", state)
print(f"表达式: entity.players.player_01.class[0].level")
print(f"结果: {result.result}")
print(f"轨迹: {result.resolved}")
print()

# 测试3: 掷骰 + 路径引用
print("=" * 50)
print("测试3: 掷骰 + 路径引用")
print("=" * 50)
expr = "Roll('1d20') + entity.players.player_01.attributes.modifiers.strength"
result = engine.eval(expr, state)
print(f"表达式: {expr}")
print(f"结果: {result.result}")
print(f"轨迹: {result.resolved}")
print()

# 测试4: 复杂表达式（多行）
print("=" * 50)
print("测试4: 复杂表达式（多行）")
print("=" * 50)
expr = """attack_roll = Roll('1d20')
if attack_roll == 20:
    result = 'critical_hit'
elif attack_roll == 1:
    result = 'critical_miss'
else:
    total = attack_roll + entity.players.player_01.attributes.modifiers.strength
    result = total
result"""
result = engine.eval(expr, state)
print(f"表达式:\n{expr}")
print(f"结果: {result.result}")
print(f"轨迹: {result.resolved}")
print()

# 测试5: 变量形式的 Roll（场景3的问题）
print("=" * 50)
print("测试5: 变量形式的 Roll")
print("=" * 50)
expr = """caster_level = entity.players.player_01.class[0].level
if caster_level >= 5:
    damage_dice = '2d8'
else:
    damage_dice = '1d8'
Roll(damage_dice)"""
try:
    result = engine.eval(expr, state)
    print(f"表达式:\n{expr}")
    print(f"结果: {result.result}")
    print(f"轨迹: {result.resolved}")
except Exception as e:
    print(f"错误: {e}")
print()

print("=" * 50)
print("所有测试完成!")
print("=" * 50)
