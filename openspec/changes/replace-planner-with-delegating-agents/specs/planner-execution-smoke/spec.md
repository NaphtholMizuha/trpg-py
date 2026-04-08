## 新增需求

## 修改需求

## 移除需求

### 需求: 系统必须提供 planner 到 engine 的端到端 smoke 入口
**Reason**: planner 到 engine 的长期回归不再通过手动 smoke 脚本表达。
**Migration**: 将端到端验证迁移到自动测试与固定评测套件。

### 需求: planner 到 engine 的端到端 smoke 必须支持正常嵌套 TOML world state
**Reason**: world state 夹具仍可保留，但不再绑定到 smoke 入口。
**Migration**: 将该要求迁移到正式评测入口或自动测试的状态装载逻辑。
