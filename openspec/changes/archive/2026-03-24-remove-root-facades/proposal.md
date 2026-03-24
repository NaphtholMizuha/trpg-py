## 为什么

`trpg_py` 包根目录目前同时承载了稳定公共 API、内部实现入口和仅用于转发的薄 facade 模块，导致目录语义不清晰，也让调用方难以判断哪些导入路径是长期稳定承诺。既然 `engine` 和 `store` 已经成为明确的实现归属，现在适合收紧包根目录边界，停止把根目录散件模块当作主要访问路径。

## 变更内容

- **BREAKING** 删除包根目录下仅用于转发的薄 facade 模块，包括 `trpg_py.dice`、`trpg_py.executor`、`trpg_py.operations`、`trpg_py.refs`、`trpg_py.models` 和 `trpg_py.state`。
- 保留 `trpg_py.__init__` 作为精简后的稳定公共 API 入口，仅导出项目承诺长期支持的顶层构件。
- 保留 `trpg_py.errors` 作为跨包共享的错误定义模块，不将其下沉为 facade。
- 要求调用方在访问具体实现时直接使用 `trpg_py.engine...` 与 `trpg_py.store...` 命名空间，而不是依赖包根目录的转发模块。
- 更新测试、示例和文档中的导入路径，使项目内部和对外说明都与新的目录边界一致。

## 功能 (Capabilities)

### 新增功能
- `root-api-layout`: 规范 `trpg_py` 包根目录只提供精简稳定公共 API，并禁止继续使用根目录薄 facade 模块作为主要访问路径。

### 修改功能
- `engine-package-layout`: 调整顶层与 `trpg_py.engine` 的导出契约，要求稳定入口集中在 `trpg_py.__init__` 与 `trpg_py.engine`，不再要求维护额外的根目录转发模块。

## 影响

- 受影响代码：`trpg_py/__init__.py`、包根目录各薄 facade 文件、依赖这些模块的测试与示例代码。
- 受影响 API：直接导入 `trpg_py.dice`、`trpg_py.executor`、`trpg_py.operations`、`trpg_py.refs`、`trpg_py.models`、`trpg_py.state` 的调用方需要迁移。
- 受影响系统：包目录结构、公开导入路径约定以及后续模块组织原则。
