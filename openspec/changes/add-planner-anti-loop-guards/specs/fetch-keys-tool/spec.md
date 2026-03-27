## 新增需求

### 需求:list 的无命中结果必须可作为缺失事实证据消费
系统必须保证 `list` 在 `status=no_match` 时表达的是“当前 state 中未找到匹配路径”，供 planner 直接作为缺失事实证据消费。禁止把 `no_match` 设计成语义模糊的“也许只是查询方式不对”，从而诱导无限重试。

#### 场景:list 在建议修正后仍无命中
- **当** 调用方向 `list` 提交一个无命中的 `prefix`
- **当** 返回体已提供建议路径或建议前缀
- **那么** 返回状态仍然必须是 `no_match`
- **那么** 调用方可以将其解释为当前 state 中缺失对应路径事实
- **那么** 建议路径只作为有限修正线索，不得伪装成命中结果

## 修改需求

### 需求:fetch_keys 返回语义必须可直接驱动 planner 分支决策
系统必须保证 `list` 的 `ok/no_match/error` 三类返回语义稳定可区分，供 planner 直接判定“路径已确认”“当前 state 中缺失对应路径事实”或“系统故障”，禁止将不同结果折叠为模糊输出。若 `list` 已返回 `status=no_match` 且提供建议路径，planner 只能基于这些建议做有限修正，而不得把同一失败主题无限当作待继续发现的问题。

#### 场景:planner 根据 no_match 触发收口
- **当** planner 使用有效前缀调用 `list` 且返回 `status=no_match`
- **那么** planner 可以将该结果解释为当前 state 中缺失对应路径事实
- **那么** planner 可以利用建议路径做有限修正或触发 `needs_human`
- **那么** planner 不得将该结果误判为系统错误
- **那么** planner 不得围绕同一失败前缀无限重试

#### 场景:planner 根据 error 触发阻塞
- **当** `list` 返回 `status=error`
- **那么** planner 可以将该结果解释为工具故障
- **那么** planner 可以进入 `blocked` 或降级流程

## 移除需求
