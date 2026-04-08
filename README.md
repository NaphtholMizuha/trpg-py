# TRPG Planner Runtime

这个项目现在的长期运行时真相是委派式 agent 架构，而不是固定的 `task_node -> dsl_node` workflow。

## 当前架构

- `augury.agent.create_planner`：主入口
- `Main Agent`：默认装配 `list_skills`、`load_skills`、`delegate`
- `Context Agent`：默认装配 `grep`、`search`
- `Context Agent`：默认装配 `grep`、`search`、`ask`
- `Resolution Agent`：默认装配 `lint`、`execute`

主流程：

1. 主 agent 接收 instruction 和 state
2. 主 agent 通过 `load_skills` 装配子 agent
3. 主 agent `delegate` 给 `Context Agent` 收集高信息密度上下文
4. 主 agent `delegate` 给 `Resolution Agent` 生成、校验并执行 `TaskDocument`
5. 调用方收到结构化结果：`ready` / `needs_human` / `blocked` / `error`

## Python 用法

```python
from augury import create_planner

state = {
    "actors": {
        "aldera": {
            "id": "aldera",
            "position": {"x": 0, "y": 0},
            "attacks": {
                "longsword": {
                    "to_hit": 7,
                    "reach": 5,
                    "damage": [{"dice": "1d8", "bonus": 4, "damage_type": "slashing"}],
                }
            },
        },
        "goblin_1": {
            "id": "goblin_1",
            "position": {"x": 0, "y": 1},
            "hp": {"current": 7, "max": 7},
            "ac": {"total": 13},
        },
    }
}

planner = create_planner(state=state)
result = planner.invoke("Aldera用长剑攻击goblin_1")

print(result.status)
print(result.task_document)
print(result.execution_report)
```

## 工具命名空间

`augury.agent.tools` 提供新的长期工具入口：

- `create_list_tool`
- `create_read_tool`
- `create_grep_tool`
- `create_search_tool`
- `create_lint_tool`
- `create_execute_tool`
- `create_list_skills_tool`
- `create_load_skills_tool`
- `create_delegate_tool`

## 配置

项目配置位于 `config/config.toml`。

`[planner]` 现在使用这些子段：

- `[planner.main_prompt]`
- `[planner.context_agent_prompt]`
- `[planner.resolution_agent_prompt]`
- `[planner.evals]`

`[planner.evals].world_state_file` 用于默认评测状态夹具。

## 自动测试

项目不再维护 `src/smoke/` 手动脚本。验证真相已经收敛到 `src/tests/` 和版本化评测夹具。

示例：

```bash
python -m unittest src.tests.test_agent_runtime
python -m unittest src.tests.test_planner_e2e_eval
python -m unittest src.tests.test_context_agent_eval
```

## 手动 Eval

`src/eval/` 用来放长期保留、结构化、可人工运行的 eval runner，而不是临时 smoke 脚本。

当前提供：

- `src/eval/context_agent_eval.py`：直接复现主 agent 委派给 `Context Agent` 的默认 payload，并打印实时 `ContextBundle`
- 该 payload 现在明确展示 `intent`、`goal`、`requests`，用来观察主 agent 是否把原始用户意图整理成了事实获取任务
- 当 `Context Agent` 触发 ask interrupt 时，CLI runner 会用标准输入输出方式展示候选项、默认值和自定义输入入口，并在同一次运行中恢复执行
- 因此交互式 CLI eval 会展示 ask interrupt、`AskResponse` 和恢复后的最终 `ContextBundle`

示例：

```bash
python src/eval/context_agent_eval.py
python src/eval/context_agent_eval.py --intent "Aldera用长剑攻击goblin_1"
python src/eval/context_agent_eval.py --intent "Aldera用火球术攻击goblin" --json
```

## 评测夹具

固定评测夹具位于：

- `examples/evals/planner_e2e/cases.json`
- `examples/evals/planner_e2e/world_state.toml`

相关 helper 位于 `augury.agent.evals`。
