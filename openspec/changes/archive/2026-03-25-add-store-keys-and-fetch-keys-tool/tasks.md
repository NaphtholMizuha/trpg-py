## 1. Store 接口扩展

- [x] 1.1 在 `trpg_py.store.core` 中新增 `keys` 接口，支持全量枚举路径
- [x] 1.2 为 `keys` 增加范围过滤参数（至少支持 `prefix`）并保持点路径格式一致
- [x] 1.3 更新 `trpg_py.store` 公开导出，确保调用方可从包级入口使用 `keys`

## 2. Fetch Keys 工具实现

- [x] 2.1 在 `trpg_py.agent.tools` 新增 `fetch_keys` 工具输入输出模型与核心逻辑
- [x] 2.2 让 `fetch_keys` 复用 `store.keys`，并保持全量/按范围语义一致
- [x] 2.3 为 `fetch_keys` 提供结构化返回语义，覆盖命中、无命中和错误场景
- [x] 2.4 如有统一工具入口，补充 `fetch_keys` 的导出与注册

## 3. 测试与文档

- [x] 3.1 为 `store.keys` 增加测试，覆盖全量枚举、按前缀枚举和空结果
- [x] 3.2 为 `fetch_keys` 增加测试，覆盖包装一致性与错误语义
- [x] 3.3 更新 README 或 agent 工具说明，明确 `fetch_keys` 的职责边界和调用示例
- [x] 3.4 新增可直接运行的 `test_fetch_keys.py` 演示脚本，展示全量枚举与按范围枚举行为
