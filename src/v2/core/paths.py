"""
路径相关数据类
"""
from dataclasses import dataclass


@dataclass
class RelevantPaths:
    """PathFinder返回的相关路径"""
    primary_paths: dict[str, str]   # {path: type}
    related_paths: dict[str, str]   # {path: type}
