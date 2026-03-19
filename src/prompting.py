"""
统一的 prompt 加载与渲染入口。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path


_PROMPT_ROOT = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=None)
def load_prompt(relative_path: str) -> str:
    """按相对路径加载 prompt 文件，并缓存内容。"""
    return (_PROMPT_ROOT / relative_path).read_text(encoding="utf-8")


def render_prompt(relative_path: str, **kwargs: object) -> str:
    """加载并格式化 prompt 模板。"""
    return load_prompt(relative_path).format(**kwargs)
