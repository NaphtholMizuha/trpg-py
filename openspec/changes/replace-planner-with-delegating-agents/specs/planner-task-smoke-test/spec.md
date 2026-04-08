## 新增需求

## 修改需求

## 移除需求

### 需求:系统必须提供专门验证 task_node 生成 TaskDraft 的 smoke 脚本
**Reason**: `task_node` smoke 不再是长期验证入口。
**Migration**: 将第一阶段或 Context Agent 的验证迁移到自动测试与固定评测。

### 需求:task smoke 脚本必须支持可配置指令与状态文件
**Reason**: 旧 task smoke 脚本将被删除。
**Migration**: 将指令与状态文件覆盖能力迁移到测试夹具或评测 manifest。

### 需求:task smoke 脚本必须暴露稳定的 TaskDraft 输出契约
**Reason**: `TaskDraft` 不再通过 smoke 脚本承载长期观察面。
**Migration**: 通过结构化测试结果或新的上下文 bundle 契约表达观察面。
