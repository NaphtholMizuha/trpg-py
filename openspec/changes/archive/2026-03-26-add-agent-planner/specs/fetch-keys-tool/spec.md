## 新增需求

### 需求:fetch_keys 返回语义必须可直接驱动 planner 分支决策
系统必须保证 `fetch_keys` 的 `ok/no_match/error` 三类返回语义稳定可区分，供 planner 直接判定“路径已确认”“信息不足”或“系统故障”，禁止将不同结果折叠为模糊输出。

#### 场景:planner 根据 no_match 触发澄清
- **当** planner 使用有效前缀调用 `fetch_keys` 且返回 `status=no_match`
- **那么** planner 可以将该结果解释为证据不足
- **那么** planner 可以触发 `needs_human` 而不是误判为系统错误

#### 场景:planner 根据 error 触发阻塞
- **当** `fetch_keys` 返回 `status=error`
- **那么** planner 可以将该结果解释为工具故障
- **那么** planner 可以进入 `blocked` 或降级流程

## 修改需求

## 移除需求
