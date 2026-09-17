from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
_guide: dict | None = None


def load_guide() -> dict:
    global _guide
    if _guide is not None:
        return _guide
    with open(DATA_DIR / "guide.json", encoding="utf-8") as f:
        _guide = json.load(f)
    return _guide
