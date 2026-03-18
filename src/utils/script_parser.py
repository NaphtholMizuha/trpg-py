"""
LLM 输出清洗辅助。
"""
from __future__ import annotations


def extract_json_block(text: str) -> str:
    """尽量从自由文本中截取最外层 JSON 对象。"""
    cleaned = (text or "").strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    json_start = cleaned.find("{")
    json_end = cleaned.rfind("}")
    if json_start >= 0 and json_end > json_start:
        return cleaned[json_start:json_end + 1]
    return cleaned
