"""
KVStateStore 单元测试
"""
import pytest
from src.tools.kv_state import KVStateStore


class TestKVStateStore:
    """测试 KV 状态存储"""

    @pytest.fixture
    def store(self, tmp_path):
        path = tmp_path / "test_state.txt"
        return KVStateStore(str(path), persist=False)

    def test_patch_add(self, store):
        """测试添加操作"""
        success, changes = store.patch([{"op": "ADD", "key": "test", "value": "value"}])
        assert success
        assert len(changes) == 1
        assert changes[0].operation == "ADD"
        assert changes[0].key == "test"
        assert changes[0].new_value == "value"

    def test_patch_mod(self, store):
        """测试修改操作"""
        store.patch([{"op": "ADD", "key": "test", "value": "old"}])
        success, changes = store.patch([{"op": "MOD", "key": "test", "value": "new"}])
        assert success
        assert changes[0].old_value == "old"
        assert changes[0].new_value == "new"

    def test_patch_del(self, store):
        """测试删除操作"""
        store.patch([{"op": "ADD", "key": "test", "value": "value"}])
        success, changes = store.patch([{"op": "DEL", "key": "test"}])
        assert success
        assert changes[0].operation == "DEL"

    def test_get_nonexistent_key(self, store):
        """测试获取不存在的 key"""
        value = store.get("nonexistent")
        assert value is None

    def test_get_keys_empty(self, store):
        """测试获取空 key 列表"""
        keys = store.get_keys()
        assert keys == []

    def test_get_keys_with_data(self, store):
        """测试获取有数据的 key 列表"""
        store.patch([
            {"op": "ADD", "key": "A.combat", "value": "HP: 10"},
            {"op": "ADD", "key": "B.combat", "value": "HP: 20"},
        ])
        keys = store.get_keys()
        assert len(keys) == 2
        assert "A.combat" in keys
        assert "B.combat" in keys

    def test_get_text(self, store):
        """测试获取完整文本"""
        store.patch([{"op": "ADD", "key": "test", "value": "value"}])
        text = store.get_text()
        assert "[test]" in text
        assert "value" in text

    def test_reload(self, store):
        """测试重新加载"""
        store.patch([{"op": "ADD", "key": "test", "value": "value"}])
        # 非持久化模式下，reload 会从文件重新加载，如果没有文件则数据会被清空
        # 这是预期行为 - reload 是用来从文件重新加载外部修改的
        store.reload()
        # 由于是非持久化模式且文件不存在，reload 后数据为空
        value = store.get("test")
        assert value is None

    def test_batch_operations(self, store):
        """测试批量操作"""
        operations = [
            {"op": "ADD", "key": "A", "value": "1"},
            {"op": "ADD", "key": "B", "value": "2"},
            {"op": "MOD", "key": "A", "value": "10"},
        ]
        success, changes = store.patch(operations)
        assert success
        assert len(changes) == 3
        assert store.get("A") == "10"
        assert store.get("B") == "2"
