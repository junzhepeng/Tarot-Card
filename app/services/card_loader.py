import json
from pathlib import Path

from app.models.card import Card
from app.models.spread import Position, Spread

DATA_DIR = Path(__file__).parent.parent / "data"

_cards: list[Card] | None = None
_spreads: list[Spread] | None = None
_cards_by_id: dict[str, Card] | None = None


def _load_json(filename: str) -> list | dict:
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def load_cards() -> list[Card]:
    global _cards, _cards_by_id
    if _cards is not None:
        return _cards
    raw = _load_json("cards.json")
    _cards = [
        Card(
            id=item["id"],
            name_zh=item["name_zh"],
            name_en=item["name_en"],
            arcana=item["arcana"],
            suit=item.get("suit"),
            number=item["number"],
            rank=item.get("rank"),
            element=item.get("element"),
            upright_keywords=item["upright_keywords"],
            reversed_keywords=item["reversed_keywords"],
            upright_meaning=item["upright_meaning"],
            reversed_meaning=item["reversed_meaning"],
            image_path=item.get("image_path", f"/static/cards/{item['id']}.jpg"),
        )
        for item in raw
    ]
    _cards_by_id = {c.id: c for c in _cards}
    return _cards


def get_card(card_id: str) -> Card | None:
    if _cards_by_id is None:
        load_cards()
    return _cards_by_id.get(card_id)


def _parse_spread_item(item: dict) -> Spread:
    positions = [
        Position(index=p["index"], label=p["label"], hint=p["hint"])
        for p in item["positions"]
    ]
    return Spread(
        id=item["id"],
        name_zh=item["name_zh"],
        category=item["category"],
        card_count=item["card_count"],
        description=item.get("description", ""),
        positions=positions,
        tips=item["tips"],
        layout=item["layout"],
    )


def load_preset_spreads() -> list[Spread]:
    raw = _load_json("spreads.json")
    return [_parse_spread_item(item) for item in raw]


def load_spreads() -> list[Spread]:
    global _spreads
    if _spreads is not None:
        return _spreads
    from app.services.spread_store import load_custom_spreads

    _spreads = load_preset_spreads() + load_custom_spreads()
    return _spreads


def get_spread(spread_id: str) -> Spread | None:
    if spread_id.startswith("custom-"):
        from app.services.spread_store import get_custom_spread

        return get_custom_spread(spread_id)
    return next((s for s in load_spreads() if s.id == spread_id), None)


def invalidate_spread_cache() -> None:
    global _spreads
    _spreads = None
