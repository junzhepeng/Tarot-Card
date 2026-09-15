from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DrawnCard:
    position_index: int
    card_id: str
    is_reversed: bool


@dataclass
class ReadingRecord:
    id: int
    question: str
    spread_id: str
    created_at: str
    notes: str
    ai_summary: Optional[str]
    cards: list[DrawnCard]
