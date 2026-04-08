## 1. Ask Tool 契约

- [x] 1.1 在 agent 工具层新增可复用的 `ask` tool 契约与数据模型，覆盖问题文本、选项、默认值和自定义输入入口
- [x] 1.2 为 ask 请求定义稳定字段与序列化边界，确保 UI、eval 和测试可以直接消费而无需解析自由文本
- [x] 1.3 明确统一 ask 契约与宿主适配层的边界，确保本次只实现 Python CLI 也不会污染长期接口

## 2. Runtime 与 Context Agent

- [x] 2.1 调整 agent runtime 的默认工具装配，使 Context Agent 可以挂载 `ask`，同时保留该工具给其他 agent 复用的入口
- [x] 2.2 调整 Context Agent 的缺口处理逻辑：在可明确提问的歧义场景中优先生成 `ask_requests`，并让它取代面向 DM 的普通缺口返回
- [x] 2.3 调整 planner / bundle 结构，使 ask 请求能够作为一等结果字段向外透出
- [x] 2.4 为当前运行路径实现 Python CLI ask adapter，把统一 AskRequest / AskResponse 接到终端交互

## 3. Prompt、Eval 与测试

- [x] 3.1 更新主 agent / Context Agent 的 prompt 或等价默认指引，明确何时使用 ask，以及如何提供候选项、默认值和自定义输入
- [x] 3.2 更新 eval 脚本或观察入口，使其能够展示 ask 请求内容及其选项结构，并与 CLI ask adapter 对齐
- [x] 3.3 增加自动测试，覆盖 ask 请求的生成、默认值语义、自定义输入入口、CLI 适配行为，以及 planner 结果对 ask 的透出

## 4. 收口

- [x] 4.1 更新相关文档或说明，解释 ask tool 为什么是通用 agent 工具而不是 Context Agent 私有能力
- [x] 4.2 运行相关测试与手动自检，确认 ask tool、Context Agent 和 planner 对外结果保持一致
