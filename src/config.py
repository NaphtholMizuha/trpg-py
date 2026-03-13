"""
统一配置管理

集中管理所有配置项，支持从环境变量加载
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import os


def _load_prompt(filename: str) -> str:
    """从 prompts 目录加载 prompt 文件"""
    prompt_path = Path(__file__).parent.parent / "prompts" / filename
    return prompt_path.read_text(encoding="utf-8")


# Agent System Prompts - 从文件加载
PLANNER_SYSTEM_PROMPT = _load_prompt("planner.md")
EXECUTOR_SYSTEM_PROMPT = _load_prompt("executor.md")
CHAIN_SYSTEM_PROMPT = _load_prompt("chain.md")


@dataclass(frozen=True)
class AppConfig:
    """应用配置"""
    # LLM 配置
    llm_model: str = "gpt-4o"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_provider: str = "openai"  # 支持: openai, deepseek, minimax

    # RAG 配置
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "dnd_5e_srd_hybrid"
    embedding_model: str = "BAAI/bge-m3"
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    siliconflow_api_key: Optional[str] = None

    # 状态存储
    world_state_path: str = "data/world_state.txt"
    persist_state: bool = False

    # 执行参数
    max_react_iterations: int = 10
    enable_dm_confirm: bool = True

    @classmethod
    def from_env(cls) -> "AppConfig":
        """从环境变量加载配置"""
        return cls(
            llm_model=os.getenv("LLM_MODEL", "gpt-4o"),
            llm_api_key=os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY"),
            llm_base_url=os.getenv("DEEPSEEK_BASE_URL"),
            llm_provider=os.getenv("LLM_PROVIDER", "openai"),
            siliconflow_api_key=os.getenv("SILICONFLOW_API_KEY"),
            persist_state=os.getenv("PERSIST_STATE", "false").lower() == "true",
        )

    @classmethod
    def from_provider(cls, provider: str = "deepseek") -> "AppConfig":
        """从提供商名称创建配置

        Args:
            provider: 模型提供商，支持 "deepseek", "minimax", "openai"
        """
        provider = provider.lower()

        if provider == "deepseek":
            return cls(
                llm_model="deepseek-chat",
                llm_api_key=os.getenv("DEEPSEEK_API_KEY"),
                llm_base_url=os.getenv("DEEPSEEK_BASE_URL"),
                llm_provider="deepseek",
            )
        elif provider == "minimax":
            return cls(
                llm_model="MiniMax-M2.5-highspeed",  # minimax-m2.5 模型名称
                llm_api_key=os.getenv("MINIMAX_API_KEY"),
                llm_base_url="https://api.minimaxi.com/v1",
                llm_provider="minimax",
            )
        elif provider == "openai":
            return cls(
                llm_model=os.getenv("LLM_MODEL", "gpt-4o"),
                llm_api_key=os.getenv("OPENAI_API_KEY"),
                llm_base_url=os.getenv("OPENAI_BASE_URL"),
                llm_provider="openai",
            )
        else:
            raise ValueError(f"不支持的提供商: {provider}，支持: deepseek, minimax, openai")
