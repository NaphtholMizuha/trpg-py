# Code Mode Rules

项目特定的编码规则，只包含非显而易见的约定。

## 核心工具使用

### KV State Storage
- 必须使用 `KVStateStore.patch()` 修改状态，返回 `(success, changes)` 元组
- Value 是自然语言段落，不是结构化数据
- 测试时必须用 `persist=False`，避免写入真实文件

### 配置初始化
- 使用 `AppConfig.from_env()` 而不是直接 `AppConfig()`
- API key 支持 DEEPSEEK_API_KEY 或 OPENAI_API_KEY

### Agent 开发
- 继承 `BaseAgent`，工具通过 `tools` 参数注入
- 自定义异常放在 `src/agents/exceptions.py`
- 子类只需实现 `run()` 方法，ReAct 循环已封装

## 导入规范

```python
# ✅ 正确 - 绝对导入
from src.tools.kv_state import KVStateStore

# ❌ 错误 - 避免相对导入
from ..tools.kv_state import KVStateStore
```

## 日志规范

```python
# ✅ 正确
from src.utils.logging import get_logger
logger = get_logger(f"{__class__.__module__}.{__class__.__name__}")

# ❌ 错误 - 不要用 print
print("debug info")
```
