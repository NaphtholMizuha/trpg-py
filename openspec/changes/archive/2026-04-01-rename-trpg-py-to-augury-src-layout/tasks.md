## 1. 目录与打包骨架

- [x] 1.1 创建 `src/augury/`、`src/smoke/` 和 `src/tests/` 目标目录，并确定旧目录到新目录的映射关系。
- [x] 1.2 更新 `pyproject.toml` 与相关工具配置，使项目以 `src` 作为 Python 源码根并以 `augury` 作为正式包命名空间。

## 2. 运行时代码迁移

- [x] 2.1 将现有 `trpg_py/` 代码迁移到 `src/augury/`，并批量更新包内相对/绝对导入到 `augury` 命名空间。
- [x] 2.2 更新公共 API、内部命名空间和配置加载代码，确保 `augury`、`augury.engine`、`augury.store`、`augury.agent` 的稳定入口可用且不再依赖旧包名。

## 3. Smoke 与自动测试迁移

- [x] 3.1 将现有 `smoke/` 脚本迁移到 `src/smoke/`，并更新脚本 bootstrap、命令示例和默认路径解析逻辑以适配 `src` 布局。
- [x] 3.2 将现有 `tests/` 套件迁移到 `src/tests/`，并更新测试导入、发现路径和与 smoke 路径相关的断言。

## 4. 文档与验证

- [x] 4.1 更新 README、命令示例和开发说明，统一改用 `augury` 导入路径以及 `src/smoke/`、`src/tests/` 命令。
- [x] 4.2 运行自动测试和关键 smoke 验证，确认 `augury` 命名空间、`src` 布局和新脚本路径在本地可正常工作。
