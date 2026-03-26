## 新增需求

### 需求:planner 必须从外置文本模板加载 prompt
planner 必须从统一配置指定的外置文本模板加载 system prompt 和 user prompt，禁止继续把长期默认 prompt 文案内嵌在 `planner.py` 中作为唯一真相。

#### 场景:planner 使用配置指定的默认 prompt 模板
- **当** 调用方通过统一配置创建 planner 且未显式覆写 prompt 来源
- **那么** planner 必须从配置指定的文本模板加载 system prompt 和 user prompt
- **那么** planner 不得继续依赖代码内联 prompt 字符串作为默认行为

### 需求:planner 必须渲染受控占位符并对模板错误快速失败
planner 必须支持把 instruction、context、policy、tool budget 和 repair feedback 等动态字段渲染到外置 prompt 模板中，并在模板文件缺失、不可读、占位符未知或渲染后仍残留未解析占位符时快速失败。

#### 场景:planner 渲染 user prompt 动态内容
- **当** planner 发起一次新的规划请求
- **那么** user prompt 模板必须能接收 instruction、context JSON、policy JSON 和 tool budget 等动态内容
- **那么** 首轮或修复轮的最终 prompt 必须来源于模板渲染结果

#### 场景:planner 在修复轮渲染 validation feedback
- **当** planner 因 schema 或语义校验失败进入修复轮
- **那么** 系统必须把 validation feedback 注入外置 user prompt 模板
- **那么** 修复轮不必回退到代码内嵌字符串拼接

#### 场景:prompt 模板装载或渲染失败
- **当** planner 配置引用了不存在的 prompt 文件、不可读文件或非法占位符
- **那么** planner 创建或调用必须快速失败
- **那么** 错误信息必须指出具体的 prompt 文件或模板问题

## 修改需求

### 需求:planner factory 必须从统一项目配置读取默认运行参数
系统必须要求 planner factory 的默认模型、接入点、超时、重试次数、规划轮数、工具预算以及默认 prompt 资源定位来自统一项目配置，而禁止继续以模块内 `DEFAULT_*` 常量、内嵌 prompt 字符串或独立路径约定作为长期配置来源。

#### 场景:planner factory 使用统一配置创建实例
- **当** 调用方未显式覆写 planner factory 的运行参数
- **那么** planner factory 从统一项目配置读取默认值
- **那么** planner 实例的运行行为与项目配置文件保持一致

#### 场景:planner factory 从统一配置读取 prompt 来源
- **当** 调用方通过统一配置创建 planner
- **那么** factory 必须从统一配置解析默认 prompt 目录与模板文件
- **那么** 最终创建出的 planner 使用该配置指定的 prompt 模板

## 移除需求
