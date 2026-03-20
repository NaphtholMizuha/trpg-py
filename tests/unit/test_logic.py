"""
LogicEngine 单元测试
"""
import pytest
from src.tools.logic import LogicEngine


class TestLogicEngine:
    """测试逻辑引擎"""

    def test_simple_roll(self):
        """测试简单掷骰"""
        engine = LogicEngine()
        result = engine.eval("Roll('1d20') + 5")
        assert isinstance(result.result, int)
        assert 6 <= result.result <= 25

    def test_dice_breakdown_in_trace(self):
        """测试掷骰轨迹包含骰子分解"""
        engine = LogicEngine()
        result = engine.eval("Roll('2d6')")
        assert "2d6" in result.resolved
        assert "=" in result.resolved

    def test_comparison_expression(self):
        """测试比较表达式"""
        engine = LogicEngine()
        result = engine.eval("Roll('1d20') + 3 >= 15")
        assert isinstance(result.result, bool)

    def test_complex_expression(self):
        """测试复杂表达式"""
        engine = LogicEngine()
        result = engine.eval("Roll('1d8') + Roll('1d6') + 3")
        assert isinstance(result.result, int)
        assert 5 <= result.result <= 17

    def test_multiple_dice(self):
        """测试多个骰子"""
        engine = LogicEngine()
        result = engine.eval("Roll('3d6')")
        assert isinstance(result.result, int)
        assert 3 <= result.result <= 18
        assert "3d6" in result.resolved
