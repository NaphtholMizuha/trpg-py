"""
工作流观察脚本

使用方式：
  python test.py                            # 默认使用 deepseek，自动确认模式
  python test.py --manual                   # 手动审批模式（使用 interrupt）
  python test.py --provider minimax         # 使用 MiniMax-M2.5（DashScope 兼容接口）
  python test.py --provider openai          # 使用 openai

当前脚本重点观察：
1. 魔法飞弹伤害即将结算时，艾尔德拉是否会获得护盾术决策窗口
2. 艾尔德拉即将施放护盾术时，马利克是否会获得法术反制决策窗口
3. 法术反制成功后，是否会阻止护盾术继续落地
4. 护盾术被阻止后，原始魔法飞弹伤害是否会正常结算

环境变量配置：
  DEEPSEEK_API_KEY      - DeepSeek API 密钥
  DEEPSEEK_BASE_URL     - DeepSeek API 地址（可选）
  DASHSCOPE_API_KEY     - DashScope API 密钥（用于 minimax 提供商）
  OPENAI_API_KEY        - OpenAI API 密钥
  OPENAI_BASE_URL       - OpenAI API 地址（可选）
"""
import os
from dataclasses import dataclass
from dataclasses import replace

import typer
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

from src.utils.logging import configure_logging
# 配置日志只输出 INFO 及以上级别
configure_logging(debug=True)

from src.workflow import create_workflow
from src.tools.kv_state import KVStateStore

app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    rich_markup_mode="rich",
    help="TRPG 阶段化结算观察脚本",
)
console = Console()


@dataclass
class Scenario:
    name: str
    user_input: str
    objective: str
    expected_now: str


def print_header(title: str):
    console.print()
    console.print(Rule(f"[bold cyan]{title}[/bold cyan]"))


def print_scenario_notes(scenario: Scenario):
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(style="bold yellow", width=10)
    table.add_column(style="white")
    table.add_row("观察目标", scenario.objective)
    table.add_row("当前预期", scenario.expected_now)
    console.print(Panel(table, title=f"场景: {scenario.name}", border_style="blue"))


def prompt_approval() -> dict[str, str]:
    action = Prompt.ask(
        "[bold]审批操作[/bold]",
        choices=["approve", "reject", "modify"],
        default="approve",
    )
    if action == "modify":
        suggestion = Prompt.ask("修改建议", default="")
        return {"action": "modify", "suggestion": suggestion}
    return {"action": action}


def prompt_decision_choice(decision_points: list[dict]) -> dict[str, str]:
    if not decision_points:
        return {"choice": "n"}

    choices = [str(i) for i in range(1, len(decision_points) + 1)] + ["n"]
    choice = Prompt.ask("选择响应", choices=choices, default="n")
    return {"choice": choice}


def run_scenario(workflow, store, scenario: Scenario, thread_id: str):
    """运行单个测试场景"""
    print_header(f"场景: {scenario.name}")
    print(f"指令: {scenario.user_input}")
    print_scenario_notes(scenario)

    # 重置状态
    store.reload()

    # V11 架构: 初始状态不包含 messages，在 invoke 时传入
    initial_state = {
        "changes": [],
        "task_queue": [],
        "_current_task": None,
        "_pending_interrupt": None,
        "_planned_message_count": 0,
        "_execution_state": None,
        "_execution_context": None,
    }

    config = {"configurable": {"thread_id": thread_id}}

    # 用于去重打印
    printed_task_id = None
    printed_phase = None
    interrupt_count = 0

    try:
        console.print("\n[bold green]开始执行[/bold green]")

        # 扁平化队列架构：使用 stream 处理 interrupt
        # 第一次调用时传入 messages
        current_input = {"messages": [HumanMessage(content=scenario.user_input)]}

        while True:
            # 执行到下一个 interrupt 或结束
            outputs = list(workflow.stream(current_input, config, stream_mode="values"))

            if not outputs:
                break

            # 获取最后的状态
            output = outputs[-1]

            # 打印当前任务（只在任务变化时打印）
            current_task = output.get("_current_task")
            if current_task and printed_task_id != id(current_task):
                console.print(f"\n[bold]当前任务[/bold]: {current_task.description}")
                console.print(f"  行动者: {current_task.actor}, 目标: {current_task.target}")
                if current_task.source == "chain":
                    console.print("  来源: 连锁触发")
                printed_task_id = id(current_task)

            execution_state = output.get("_execution_state")
            if execution_state and execution_state.phase_index < len(execution_state.phases):
                current_phase = execution_state.phases[execution_state.phase_index]
                if current_phase != printed_phase:
                    console.print(f"\n[cyan]当前结算阶段[/cyan]: {current_phase}")
                    if execution_state.resolution_effects:
                        console.print(f"  已记录修正效果: {execution_state.resolution_effects}")
                    printed_phase = current_phase

            execution_context = output.get("_execution_context")
            if execution_context and execution_context.get("relevant_keys"):
                console.print(f"\n[blue]本轮注入上下文[/blue]: {execution_context.get('relevant_keys')}")

            # 检查是否中断 (LangGraph interrupt 机制)
            # 注意: interrupt() 会在状态中留下 __interrupt__ 标记
            interrupt_data = output.get("__interrupt__")
            if interrupt_data:
                interrupt_count += 1
                # 统一处理 __interrupt__ 的各种可能类型
                # 可能是: tuple/list, Interrupt 对象, 或直接的 dict
                interrupt_value = interrupt_data

                # 解包容器类型
                if isinstance(interrupt_data, (tuple, list)) and len(interrupt_data) > 0:
                    interrupt_value = interrupt_data[0]

                # 解包 Interrupt 对象
                if hasattr(interrupt_value, 'value'):
                    interrupt_value = interrupt_value.value

                interrupt_info = interrupt_value if isinstance(interrupt_value, dict) else {}
                interrupt_type = interrupt_info.get("type", "unknown")

                if interrupt_type == "task_approval":
                    console.print(f"\n[bold yellow]任务审批[/bold yellow] [dim](Interrupt #{interrupt_count})[/dim]")
                    task = interrupt_info.get("task", {})
                    console.print(f"  任务: {task.get('description', 'N/A')}")
                    console.print(f"  选项: {interrupt_info.get('options', [])}")

                    # 自动确认模式下自动批准
                    if os.getenv("TRPG_AUTO_CONFIRM") == "1":
                        console.print("  [green]自动批准[/green]")
                        current_input = Command(resume={"action": "approve"})
                        continue
                    else:
                        current_input = Command(resume=prompt_approval())
                        continue

                elif interrupt_type == "decision_point_choice":
                    console.print(f"\n[bold magenta]决策窗口[/bold magenta] [dim](Interrupt #{interrupt_count})[/dim]")
                    decision_points = interrupt_info.get("decision_points", [])
                    table = Table(show_header=True, header_style="bold magenta")
                    table.add_column("#", width=3)
                    table.add_column("决策者", width=12)
                    table.add_column("时机", width=20)
                    table.add_column("选项", width=16)
                    table.add_column("说明")
                    for i, point in enumerate(decision_points, 1):
                        table.add_row(
                            str(i),
                            str(point.get("decider")),
                            str(point.get("timing")),
                            str(point.get("option_name")),
                            str(point.get("description")),
                        )
                        metadata = point.get("metadata") or {}
                        if metadata:
                            console.print(f"  metadata[{i}]: {metadata}")
                    console.print(table)
                    console.print("  n. 不触发任何响应")

                    if os.getenv("TRPG_AUTO_CONFIRM") == "1":
                        if decision_points:
                            console.print("  [green]自动选择第一个响应[/green]")
                            current_input = Command(resume={"choice": "1"})
                        else:
                            current_input = Command(resume={"choice": "n"})
                        continue
                    else:
                        current_input = Command(resume=prompt_decision_choice(decision_points))
                        continue

            # 打印队列状态
            queue = output.get("task_queue", [])
            if queue and len(queue) > 0:
                console.print(f"\n[dim]任务队列[/dim]: {len(queue)} 个待处理")

            # 检查是否结束（没有更多任务）
            if not current_task and not queue:
                console.print("\n[bold green]场景执行完成[/bold green]")
                break

            # 继续执行 - 不传 state，让 LangGraph 从 checkpoint 恢复
            current_input = None

    except Exception as e:
        console.print(f"\n[bold red]执行失败[/bold red]: {e}")
        import traceback
        traceback.print_exc()


@app.command()
def main(
    manual: bool = typer.Option(False, "--manual", help="启用手动审批模式（默认自动确认）"),
    provider: str = typer.Option(
        "deepseek",
        "--provider",
        help="选择 LLM 提供商",
        case_sensitive=False,
        show_choices=True,
    ),
):
    provider = provider.lower()
    if provider not in {"deepseek", "minimax", "openai"}:
        raise typer.BadParameter("provider 必须是 deepseek / minimax / openai")

    # 只有在没有 --manual 参数时才设置自动确认
    if not manual:
        os.environ["TRPG_AUTO_CONFIRM"] = "1"
        console.print("[green]自动确认模式[/green]（使用 --manual 启用手动审批）")
    else:
        os.environ.pop("TRPG_AUTO_CONFIRM", None)
        console.print("[yellow]手动审批模式[/yellow]")

    print_header("TRPG 阶段化结算观察")
    console.print(f"  LLM 提供商: [bold]{provider}[/bold]")

    # 根据提供商加载配置
    from src.config import AppConfig
    config = AppConfig.from_provider(provider)

    if provider == "minimax":
        config = replace(
            config,
            llm_model="MiniMax-M2.5",
            llm_api_key=os.getenv("DASHSCOPE_API_KEY"),
            llm_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    # 加载世界状态
    console.print("\n[bold blue]加载世界状态[/bold blue]...")
    store = KVStateStore("data/world_state.txt")
    console.print(f"  加载了 {len(store.get_keys())} 个状态键")

    # 检查API配置
    if not config.llm_api_key:
        provider_env = {
            "deepseek": "DEEPSEEK_API_KEY",
            "minimax": "DASHSCOPE_API_KEY",
            "openai": "OPENAI_API_KEY"
        }
        env_var = provider_env.get(provider, "API_KEY")
        console.print(f"\n[yellow]未配置 {env_var}，将使用 fallback 模式[/yellow]")

    console.print("\n[bold blue]创建工作流[/bold blue]...")
    workflow, store = create_workflow(
        world_state_path="data/world_state.txt",
        model=config.llm_model,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url
    )
    console.print(f"  工作流创建成功 (模型: [bold]{config.llm_model}[/bold])")

    scenario = Scenario(
        name="magic_missile_shield_counterspell",
        user_input="马利克对艾尔德拉施放魔法飞弹。理想情况中魔法飞弹伤害即将结算的时候，艾尔德拉可以反应施放护盾术，而艾尔德拉即将施放护盾术时，马利克可以施放法术反制。",
        objective="观察系统是否支持一条完整的响应链：魔法飞弹即将结算时出现护盾术窗口，而护盾术即将施放时再出现法术反制窗口。",
        expected_now="理想情况下，先看到艾尔德拉的护盾术决策窗口；若选择护盾术，再看到马利克的法术反制窗口；若法术反制成功，护盾术不应落地，随后魔法飞弹伤害应继续正常结算。"
    )

    run_scenario(workflow, store, scenario, "scene_magic_missile_shield_counterspell")

    print_header("观察结束")


if __name__ == "__main__":
    app()
