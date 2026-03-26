## 1. 统一配置扩展

- [x] 1.1 扩展 `trpg_py.config` 的 planner 配置模型，加入 prompt 目录与 system/user 模板文件字段，并补充路径解析与校验
- [x] 1.2 更新 `config/config.toml` 示例，把 prompt 目录与默认模板文件纳入统一配置
- [x] 1.3 在 `config/` 下新增默认 planner prompt 文本模板，确保可直接编辑和提交

## 2. Planner prompt 外置

- [x] 2.1 将 `trpg_py/agent/planner.py` 的内嵌 system/user prompt 替换为“加载外置模板 + 渲染受控占位符”
- [x] 2.2 为 prompt 模板加载、占位符渲染、缺失文件和非法占位符补充快速失败逻辑
- [x] 2.3 确保修复轮仍通过外置模板注入 `validation_feedback`，不回退到代码内联拼接

## 3. 验证与文档

- [x] 3.1 为配置加载与 planner 增加测试，覆盖 prompt 路径解析、模板渲染成功和失败场景
- [x] 3.2 更新 README 或相关说明，告知如何在 `config/` 下调试 prompt 文本以及如何通过 `config.toml` 切换目录
- [x] 3.3 运行相关测试并记录任何仍未覆盖的外部依赖限制
