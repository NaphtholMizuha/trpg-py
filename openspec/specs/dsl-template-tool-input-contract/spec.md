# dsl-template-tool-input-contract 规范

## 目的
待定 - 由归档变更 restrict-template-input-and-raise-tool-budget 创建。归档后请更新目的。
## 需求
### 需求:template 输入必须使用受控枚举类型
系统必须要求 `template` 工具的输入字段使用受控枚举类型，禁止继续以普通自由字符串接收 `task_family`、`resolution_mode`、`resource_mode`、`targeting_mode` 或 `success_rule`。

#### 场景:调用方传入合法模板查询
- **当** 调用方向 `template` 提交模板查询
- **那么** 每个输入字段都必须来自系统定义的有限枚举值集合
- **那么** `unknown` 必须作为文档化的合法保守值之一

### 需求:template 必须对非法枚举输入快速失败
系统必须让 `template` 对非法输入值产生受控失败，禁止把非法枚举值悄悄当作普通 no-match。

#### 场景:调用方传入非法 task_family
- **当** 调用方向 `template` 提交如 `area_spell` 这类不在枚举中的值
- **那么** 工具必须返回结构化错误或等价可观察失败
- **那么** 失败信息必须能够指出哪个字段不合法
- **那么** 工具不得把该值静默降级成 `unknown`

