## 新增需求

### 需求:Python CLI eval 路径必须能够按 ask 契约采集回答
系统必须允许 Python CLI 下的 eval 调用方按统一 `AskRequest` 契约实际采集 DM 回答，并将其整理成统一 `AskResponse` 结果。系统禁止让 eval 路径只能展示 ask 请求却不能按同一协议回填回答。

#### 场景:CLI eval 采集默认选项
- **当** eval 调用方在 Python CLI 中收到带默认值的 ask 请求并直接确认默认项
- **那么** 系统必须生成对应的 `AskResponse`
- **那么** 该响应必须保留问题 ID 和默认选项选择结果

#### 场景:CLI eval 采集自定义输入
- **当** eval 调用方在 Python CLI 中为 ask 请求输入候选之外的自定义答案
- **那么** 系统必须生成对应的 `AskResponse`
- **那么** 该响应必须保留问题 ID 和自定义输入值

## 修改需求

## 移除需求
