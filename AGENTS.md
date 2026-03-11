# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Build/Test/Lint Commands

```bash
# 安装依赖
uv pip install -e ".[dev]"

# 运行所有测试
pytest

# 运行单个测试
pytest tests/unit/test_kv_state.py::TestKVStateStore::test_patch_add -v

# 运行并显示覆盖率
pytest --cov=src --cov-report=term-missing
```

## Code Style

- **Python**: 3.12+ with PEP 585 type hints (`dict`, `list`, `str | None` instead of `Optional`)
- **Imports**: 绝对导入 `from src.tools.kv_state import KVStateStore`，避免相对导入 `..module`
- **Naming**: 类用 PascalCase，函数/变量用 snake_case，常量用大写 SNAKE_CASE
- **Logs**: 使用 `structlog` 通过 `get_logger(__name__)` 获取，不要用 `print`
- **Exceptions**: 自定义异常放在 `src/agents/exceptions.py`

## Key Patterns (Non-Obvious)

### KV State Storage
- 所有状态存储通过 [`KVStateStore`](src/tools/kv_state.py:21) 类
- 格式: `[Key] Value`，Value 是自然语言段落（不是结构化数据）
- 修改状态必须使用 `patch()` 方法，返回 `(success, changes)` 元组
- 测试时始终使用 `persist=False`，避免写入真实文件

### Configuration
- 配置从环境变量加载，支持 DEEPSEEK_API_KEY 或 OPENAI_API_KEY
- 初始化时用 `AppConfig.from_env()`，不用直接实例化

### Agents
- 所有 Agent 继承 [`BaseAgent`](src/agents/base.py:18)，封装 ReAct 循环
- 工具通过 `tools` 参数注入，自动绑定到 LLM
- 子类只需实现 `run()` 方法

### Logging
- 调用 `configure_logging(debug=True)` 切换到控制台输出（默认 JSON）
- Logger 命名规范: `get_logger(f"{__class__.__module__}.{__class__.__name__}")`

## Environment Variables

```bash
DEEPSEEK_API_KEY=xxx          # 或 OPENAI_API_KEY
DEEPSEEK_BASE_URL=xxx         # 可选，自定义 API 地址
SILICONFLOW_API_KEY=xxx       # 用于 embedding
PERSIST_STATE=true            # 是否持久化 world_state.txt
```
