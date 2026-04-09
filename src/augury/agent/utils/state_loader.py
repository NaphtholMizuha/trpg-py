from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def load_toml_state(path: str | Path) -> dict[str, Any]:
    payload = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("state file must contain a TOML table/object at the root")
    return payload
