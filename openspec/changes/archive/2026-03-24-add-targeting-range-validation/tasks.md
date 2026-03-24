## 1. 规格落地

- [x] 1.1 在执行模型中定义 `args.targeting` 的校验结构，覆盖 `source_position`、`max_range` 和 `range_metric`
- [x] 1.2 在选择类操作中实现 `select.target` 的 source 到 target 距离校验
- [x] 1.3 在选择类操作中实现 `select.area` 的 source 到 origin 距离校验

## 2. 报告与示例

- [x] 2.1 更新标准化执行报告与 `main.py` 展示，使超距失败和空目标结果可区分
- [x] 2.2 调整或新增示例任务 JSON，展示 `select.target` 与 `select.area` 的 targeting 写法

## 3. 验证

- [x] 3.1 为 `select.target` 的合法距离与超距失败补充测试
- [x] 3.2 为 `select.area` 的合法选点、超距失败和合法空结果补充测试
- [x] 3.3 运行相关测试与示例，确认变更符合 spec
