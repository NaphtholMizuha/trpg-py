"""
pytest 配置和 fixtures
"""
import pytest
from pathlib import Path

from src.tools.kv_state import KVStateStore
from src.tools.logic import LogicEngine


@pytest.fixture
def temp_state_store(tmp_path):
    """创建临时状态存储"""
    path = tmp_path / "test_state.txt"
    return KVStateStore(str(path), persist=False)


@pytest.fixture
def logic_engine():
    """创建逻辑引擎"""
    return LogicEngine()


@pytest.fixture
def sample_world_state():
    """示例世界状态"""
    return {
        "Aldera.combat": "HP: 44/44 | AC: 18 | 攻击加值: +7 | 武器: +1长剑 (1d8+5挥砍)",
        "Goblin.combat": "HP: 10/10 | AC: 15 | 攻击加值: +4 | 武器: 弯刀 (1d6+2挥砍)",
    }
