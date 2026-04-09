## 新增需求

### 需求:agent 包根不得长期保留已迁移 helper 的过渡模块
系统必须将 `src/augury/agent/` 包根收敛为长期入口和核心实现所在位置。对于已经迁移到 `agent/utils/` 的 helper，系统禁止继续长期保留与之等价的根级过渡模块。

#### 场景:维护者查看 agent 包根目录
- **当** 维护者查看 `src/augury/agent/` 包根
- **那么** 包根必须主要包含长期公共入口、核心模型、主 orchestration 模块和稳定子目录
- **那么** 已迁移 helper 的根级 shim 不得继续作为常驻文件存在

#### 场景:维护者完成 helper 迁移后收口
- **当** 某个 CLI、eval、state-loading 或 guard helper 已稳定迁移到 `agent/utils/`
- **那么** 对应的根级模块必须被删除
- **那么** 系统不得要求维护者继续同时维护根级 shim 和 `utils/` 真相

## 修改需求

### 需求: 运行时代码必须以 augury 作为唯一长期包命名空间
系统必须将正式运行时代码组织在 `src/augury/` 下，并以 `augury` 作为唯一长期公共导入命名空间。对于 `augury.agent` 包，系统必须进一步要求包根只保留长期入口与核心实现；在 helper 已迁入 `utils/` 后，系统禁止继续把根级兼容 shim 保留为新的长期规范入口。

#### 场景:调用方导入正式运行时代码
- **当** 调用方需要访问公共运行时 API 或内部命名空间
- **那么** 导入路径指向 `augury`、`augury.engine`、`augury.agent` 或 `augury.store`
- **那么** 系统不得要求新代码继续以 `trpg_py` 作为长期导入前缀

#### 场景:维护者查看 agent 包内部布局
- **当** 维护者查看 `src/augury/agent/` 目录结构
- **那么** 主编排入口必须以语义清晰的模块名存在
- **那么** `models.py` 可以作为共享数据契约留在包根
- **那么** 已迁移到 `utils/` 的 helper 不得继续在包根保留等价 shim

## 移除需求
