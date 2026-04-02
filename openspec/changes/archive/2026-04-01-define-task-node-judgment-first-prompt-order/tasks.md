## 1. Prompt Order

- [x] 1.1 更新 `planner_task_node_system` prompt，明确内部顺序为“可选 search -> judgments -> grep 绑定 reads/writes/missing_info/assumptions”。
- [x] 1.2 更新 `planner_task_node_user` prompt，明确 reads/writes/missing_info/assumptions 必须由 judgments 派生。

## 2. Few-shot Alignment

- [x] 2.1 调整或新增 few-shot，展示 judgments 先形成、再绑定 paths 的过程。
- [x] 2.2 在 few-shot 中展示 rule-first 任务如何先 search，再根据 judgments 使用 grep。

## 3. Validation

- [x] 3.1 更新 smoke 或相关测试，验证 prompt 文案已经体现 judgment-first 顺序。
- [x] 3.2 更新 smoke 或相关测试，验证典型规则驱动任务中 judgments 与 reads/writes 的对齐度有所提升。
