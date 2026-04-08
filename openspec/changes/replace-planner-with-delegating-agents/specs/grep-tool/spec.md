## 新增需求

### 需求:grep 返回结果必须可直接作为 Context Agent 的状态证据输入
系统必须保证 `grep` 的返回结构足够稳定，使 Context Agent 可以直接将命中结果整理为状态证据，而不是先把命中重新转换为另一套临时文本格式。

#### 场景:Context Agent 消费 grep 结果
- **当** Context Agent 调用 `grep` 获取状态事实
- **那么** 返回结果必须保留真实命中的扁平化状态行
- **那么** Context Agent 可以直接基于这些命中构造高信息密度状态证据

## 修改需求

### 需求: grep 返回语义必须可直接驱动 planner 上下文收集
系统必须保证 `grep` 的返回结果足够稳定，使 Context Agent 或其他调用方可以直接把命中的扁平化行用作结构化上下文收集输入，而不是必须再推断这些命中对应的状态事实。

#### 场景:Context Agent 直接消费 grep 命中行
- **当** Context Agent 调用 `grep` 获取状态事实
- **那么** Context Agent 必须可以直接把命中的扁平化行收集为状态证据
- **那么** 调用方无需先把路径候选再二次转换成可读事实文本

## 移除需求

### 需求: grep 工具必须提供可手动运行的 smoke 脚本
**Reason**: `grep` 的长期验证真相不再通过 smoke 脚本表达。
**Migration**: 将 `grep` 的真实链路验证迁移到自动测试与固定评测，而不是保留 `smoke/test_grep.py`。
