"""评测 case 加载。"""

from __future__ import annotations

import json
from pathlib import Path

from .models import (
    CaseModel,
    EvalCaseType,
    ExecutorEvalCase,
    PlannerEvalCase,
    ResolverEvalCase,
    WorkflowEvalCase,
)

CASE_MODEL_BY_TYPE = {
    "planner": PlannerEvalCase,
    "executor": ExecutorEvalCase,
    "resolver": ResolverEvalCase,
    "workflow": WorkflowEvalCase,
}


def load_case_file(path: str | Path, case_type: EvalCaseType) -> CaseModel:
    """加载单个 JSON case 文件。"""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"case 文件不存在: {file_path}")
    if file_path.suffix.lower() != ".json":
        raise ValueError(f"当前仅支持 .json case 文件: {file_path}")

    model = CASE_MODEL_BY_TYPE[case_type]
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    return model.model_validate(payload)


def load_cases(case_type: EvalCaseType, root: str | Path) -> list[CaseModel]:
    """加载目录下全部 JSON case。"""
    root_path = Path(root)
    if not root_path.exists():
        raise FileNotFoundError(f"case 目录不存在: {root_path}")
    files = sorted(
        file_path
        for file_path in root_path.iterdir()
        if file_path.is_file() and file_path.suffix.lower() == ".json"
    )
    return [load_case_file(file_path, case_type) for file_path in files]
