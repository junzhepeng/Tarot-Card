from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Position:
    index: int
    label: str
    hint: str


@dataclass
class Spread:
    id: str
    name_zh: str
    category: str
    card_count: int
    description: str
    positions: list[Position]
    tips: str
    layout: dict[str, Any]

    def get_position(self, index: int) -> Position:
        return self.positions[index]
