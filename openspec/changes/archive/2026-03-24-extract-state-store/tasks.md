## 1. 状态存储包骨架

- [x] 1.1 设计并创建独立于 `engine` 的状态存储包目录与导出结构
- [x] 1.2 实现点路径解析与底层读写能力，保持现有错误语义与深拷贝行为
- [x] 1.3 定义并实现 `read`、`reads`、`write`、`writes`、`mod`、`mods` 六个公开接口

## 2. 兼容层与迁移

- [x] 2.1 让 `trpg_py/state.py` 与必要旧导出转发到新状态存储包
- [x] 2.2 将 `trpg_py/refs.py` 迁移到新状态存储接口之上
- [x] 2.3 将 `trpg_py/engine/executor.py` 的状态提交逻辑迁移到新状态存储接口
- [x] 2.4 将 `trpg_py/engine/operations.py` 中直接路径访问迁移到新状态存储接口
- [x] 2.5 更新 `trpg_py/engine/__init__.py` 与相关导出，明确新推荐入口

## 3. 验证与收尾

- [x] 3.1 为路径解析、批量读写和修改接口补充单元测试
- [x] 3.2 为 executor、operations、refs 的迁移补充回归测试
- [x] 3.3 盘点代码库中剩余的旧状态工具调用，并确认是否还需要保留兼容层
