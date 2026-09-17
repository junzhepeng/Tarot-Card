from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Card:
    id: str
    name_zh: str
    name_en: str
    arcana: str  # major | minor
    suit: Optional[str]  # wands | cups | swords | pentacles | None
    number: int
    rank: Optional[str]
    element: Optional[str]
    upright_keywords: list[str]
    reversed_keywords: list[str]
    upright_meaning: str
    reversed_meaning: str
    image_path: str = ""

    @property
    def display_name(self) -> str:
        return f"{self.name_zh} ({self.name_en})"

    @property
    def is_court(self) -> bool:
        return self.rank in ("page", "knight", "queen", "king")

    @property
    def image_url(self) -> str:
        return self.image_path or f"/static/cards/{self.id}.jpg"
