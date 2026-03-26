## 1. 集成测试目录布局

- [x] 1.1 创建 `smoke/` 目录，并确定 engine/search/fetch_keys/planner 手动脚本的目标路径。
- [x] 1.2 清理根目录脚本布局，确保迁移完成后不再长期保留等价的根目录 `test*` 手动入口。

## 2. 现有脚本迁移

- [x] 2.1 将当前 `main.py` 迁移并重命名为 `smoke/test_engine.py`，同步更新其内部路径解析与命令示例。
- [x] 2.2 将 `test_fetch_keys.py` 迁移到 `smoke/test_fetch_keys.py`，保持可手动运行行为不变。
- [x] 2.3 将 `test_search.py` 迁移到 `smoke/test_search.py`，保持可手动运行行为不变。

## 3. Planner 集成脚本

- [x] 3.1 新增 `smoke/test_planner.py`，支持用示例 state 和 DM 指令触发一次 planner 调用。
- [x] 3.2 让 planner 集成脚本能够清晰展示 `ready`、`needs_human` 或 `blocked` 的结果摘要。

## 4. 文档与验证

- [x] 4.1 更新 README 与相关使用说明，统一改为新的集成测试目录命令。
- [x] 4.2 更新或新增测试，验证脚本新路径、demo 入口重命名以及 planner 集成脚本的基础可运行性。
