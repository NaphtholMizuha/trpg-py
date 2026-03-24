## 1. store 包结构重组

- [x] 1.1 创建 `trpg_py/store/` 包及包级导出文件
- [x] 1.2 将现有 `trpg_py/store.py` 的实现迁移到包内模块
- [x] 1.3 删除或停用旧的单文件 `trpg_py/store.py`，确保实现只保留一份

## 2. engine core/combat 架构重构

- [x] 2.1 创建 `trpg_py/engine/core/` 与 `trpg_py/engine/combat/` 包结构
- [x] 2.2 将 executor、refs、models、dice 等通用运行时能力迁移到 `engine.core`
- [x] 2.3 将 combat 相关操作迁移到 `engine.combat`
- [x] 2.4 更新 `trpg_py.engine` 包级导出，保持稳定入口

## 3. 拆分 operations

- [x] 3.1 将当前大号 `trpg_py/engine/operations.py` 拆分为多个按职责组织的 combat 模块
- [x] 3.2 保留一个轻量的 combat 分派入口，避免调用方直接依赖拆分细节
- [x] 3.3 检查拆分后辅助函数的归属，避免出现新的巨型模块

## 4. 兼容层与验证

- [x] 4.1 更新 `trpg_py.state`、`trpg_py.engine.state` 与必要旧入口使其转发到新布局
- [x] 4.2 更新依赖 `trpg_py.store`、`trpg_py.operations`、`trpg_py.engine` 的导入与导出，确保入口稳定
- [x] 4.3 检查并消除因重组引入的循环依赖风险
- [x] 4.4 为新的 store/engine 包布局补充或更新结构性测试
- [x] 4.5 运行现有状态、executor、operations 相关测试，确认行为未回归
