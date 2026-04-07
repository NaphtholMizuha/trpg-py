## 1. Prompt 边界建模

- [ ] 1.1 在 `config/prompts/planner_task_node_system.txt` 中加入关于 `dsl node` 与 `engine` 下游阶段职责的明确说明
- [ ] 1.2 在 `config/prompts/planner_task_node_system.txt` 中收紧 `missing_info` 语义，明确只有真实前置缺口才能进入该字段
- [ ] 1.3 在 `config/prompts/planner_task_node_user.txt` 的 requirements 中加入“运行期随机结果不属于 missing_info”的规则

## 2. Few-shot 与示例

- [ ] 2.1 增加一个攻击或法术示例，展示掷骰结果、伤害结果、豁免成败应保留在执行计划中，而不是写入 `missing_info`
- [ ] 2.2 增加一个对比例子，展示真正缺失的路径或规则身份仍然必须进入 `missing_info`

## 3. 测试与验证

- [ ] 3.1 更新 `src/tests/test_planner_workflow.py`，断言 task_node prompt 明确提到下游 `dsl node` / `engine`
- [ ] 3.2 增加 prompt 断言，验证随机性相关数值被明确定义为非 `missing_info`
- [ ] 3.3 增加 smoke 或 prompt 级验证案例，覆盖“火球术 / 攻击掷骰 / 伤害骰”这类运行期随机结果场景
