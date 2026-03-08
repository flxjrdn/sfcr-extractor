from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_manual_overrides(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = data.get("overrides", [])
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        if "doc_id" not in r or "field_id" not in r:
            continue
        out.append(r)
    return out
