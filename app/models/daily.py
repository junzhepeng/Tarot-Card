from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DailyEntry:
    id: int
    entry_date: str
    card_id: str
    is_reversed: bool
    notes: str
    created_at: str
