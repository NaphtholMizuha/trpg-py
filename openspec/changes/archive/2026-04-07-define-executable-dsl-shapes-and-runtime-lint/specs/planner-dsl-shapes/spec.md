## 新增需求

### 需求:系统必须为 dsl_node 提供统一的合法 DSL 形状目录
系统必须提供一份统一的合法 `TaskDocument` 形状目录，覆盖当前 engine 支持的 `type.kind` 组合及其 canonical 参数模板，禁止继续只靠 prompt 中零散的 few-shot 和词表来隐式约束 `dsl_node`。

#### 场景:系统列出受支持 primitive 的合法模板
- **当** 调用方需要知道某个受支持的 `type.kind` 应该如何构造
- **那么** 系统必须能够提供该 primitive 的 canonical 参数模板
- **那么** 模板必须明确哪些字段是必填、哪些字段是允许的、以及哪些形状被禁止

### 需求:合法 DSL 形状目录必须覆盖禁止形状
系统必须让合法 DSL 形状目录不仅定义正向模板，也定义常见禁止形状，禁止让 `dsl_node` 和开发者只能从 runtime 错误里反推哪些嵌套或字段写法不被支持。

#### 场景:select.area 的非法嵌套形状
- **当** 某个候选 `TaskDocument` 使用 `select.area`
- **那么** 系统必须能明确区分 `shape: "sphere"` 这类合法写法与 `shape: {type: "sphere", radius: 20}` 这类禁止写法
- **那么** `dsl_node` prompt 和相关校验都必须能消费这一区分

## 修改需求

## 移除需求
