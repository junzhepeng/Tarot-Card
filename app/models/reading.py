from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DrawnCard:
    position_index: int
    card_id: str
    is_reversed: bool
    card_type: str = "spread"
    clarifies_position: Optional[int] = None
    id: Optional[int] = None


@dataclass
class ReadingRecord:
    id: int
    question: str
    spread_id: str
    created_at: str
    notes: str
    ai_summary: Optional[str]
    cards: list[DrawnCard]
    category: str = ""
    outcome_status: str = "pending"
    outcome_notes: str = ""
    reviewed_at: Optional[str] = None

    @property
    def spread_cards(self) -> list[DrawnCard]:
        return [c for c in self.cards if c.card_type == "spread"]

    @property
    def clarifiers(self) -> list[DrawnCard]:
        return [c for c in self.cards if c.card_type == "clarifier"]
