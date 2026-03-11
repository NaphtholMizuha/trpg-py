# Debug Mode Rules

调试项目时的非显而易见规则。

## 日志配置

- 默认输出 JSON 格式，调用 `configure_logging(debug=True)` 切换到控制台可读格式
- 日志级别：DEBUG 显示所有信息，INFO 只显示关键信息

## 状态存储调试

- `KVStateStore` 使用 `persist=False` 时只在内存操作，不会写入文件
- 检查 `world_state.txt` 时注意文件锁（fcntl）可能导致并发问题

## 测试调试

- 运行单个测试: `pytest tests/unit/test_kv_state.py::TestKVStateStore::test_patch_add -v`
- 使用 `-s` 参数显示 print 输出（但项目中应避免使用 print）

## 环境变量

调试时可能需要设置：
```bash
PERSIST_STATE=false     # 避免测试污染真实状态文件
```
