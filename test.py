"""
工作流观察脚本

使用方式：
  python test.py                            # 默认使用 deepseek-chat，自动确认模式
  python test.py --manual                   # 手动审批模式（使用 interrupt）
  python test.py --provider deepseek        # 使用 deepseek-chat
  python test.py --provider minimax         # 使用 MiniMax-M2.5
  python test.py --provider kimi            # 使用 kimi-for-coding
  python test.py --provider openai          # 使用 openai

当前脚本重点观察：
1. planner 是否生成简洁的 Markdown 执行稿
2. executor 是否按步骤推进执行状态
3. 任务是否在不引入返工/补丁流程的情况下稳定结束

环境变量配置：
  DEEPSEEK_API_KEY      - DeepSeek API 密钥
  DEEPSEEK_BASE_URL     - DeepSeek API 地址（可选，默认 https://api.deepseek.com/v1）
  MINIMAX_API_KEY       - MiniMax API 密钥
  KIMI_API_KEY          - Kimi API 密钥
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


def extract_markdown_section(markdown: str, title: str) -> str:
    marker = f"## {title}"
    start = markdown.find(marker)
    if start < 0:
        return ""

    remainder = markdown[start + len(marker):]
    next_header = remainder.find("\n## ")
    section = remainder[:next_header] if next_header >= 0 else remainder
    return section.strip()


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


def run_scenario(workflow, store, scenario: Scenario, thread_id: str):
    """运行单个测试场景"""
    print_header(f"场景: {scenario.name}")
    print(f"指令: {scenario.user_input}")
    print_scenario_notes(scenario)

    # 重置状态
    store.reload()

    config = {"configurable": {"thread_id": thread_id}}

    # 用于去重打印
    printed_task_id = None
    printed_script_snapshot = None
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
                if current_task.context and "## Task Summary" in current_task.context:
                    steps_section = extract_markdown_section(current_task.context, "Execution Steps")
                    hints_section = extract_markdown_section(current_task.context, "Planner Hints")
                    snapshot = (steps_section, hints_section)
                    if snapshot != printed_script_snapshot:
                        if steps_section:
                            console.print("\n[bold blue]Execution Steps[/bold blue]")
                            console.print(steps_section[:1200], markup=False)
                        if hints_section:
                            console.print("\n[bold blue]Planner Hints[/bold blue]")
                            console.print(hints_section[:800], markup=False)
                        printed_script_snapshot = snapshot
                printed_task_id = id(current_task)

            execution_script = output.get("_execution_script")
            if execution_script and execution_script.active_step_id:
                console.print(f"\n[cyan]当前执行步骤[/cyan]: {execution_script.active_step_id}")

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
    if provider not in {"deepseek", "minimax", "kimi", "openai"}:
        raise typer.BadParameter("provider 必须是 deepseek / minimax / kimi / openai")

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
            llm_api_key=os.getenv("MINIMAX_API_KEY"),
            llm_base_url="https://api.minimaxi.com/v1",
        )

    # 加载世界状态
    console.print("\n[bold blue]加载世界状态[/bold blue]...")
    store = KVStateStore("data/world_state.txt")
    console.print(f"  加载了 {len(store.get_keys())} 个状态键")

    # 检查API配置
    if not config.llm_api_key:
        provider_env = {
            "deepseek": "DEEPSEEK_API_KEY",
            "minimax": "MINIMAX_API_KEY",
            "kimi": "KIMI_API_KEY",
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
        user_input="马利克对艾尔德拉施放魔法飞弹。",
        objective="观察在 DM 只描述主动作时，combat skill 是否仍能依据状态与规则自行推导出护盾术与法术反制这条响应链。",
        expected_now="理想情况下，即使 DM 没有额外提醒，也能先看到围绕魔法飞弹主步骤的执行稿，以及指向护盾术/法术反制的 Planner Hints；执行阶段应稳定推进，或在无法推进时直接结束当前任务，而不是进入返工/补丁流程。"
    )

    run_scenario(workflow, store, scenario, "scene_magic_missile_shield_counterspell")

    print_header("观察结束")


if __name__ == "__main__":
    app()
