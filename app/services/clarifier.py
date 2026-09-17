from __future__ import annotations

from dataclasses import dataclass

from app.models.card import Card
from app.models.spread import Position
from app.services.card_loader import get_card


@dataclass
class ClarifierReading:
    id: int
    clarifies_position: int
    position_label: str
    position_hint: str
    original_card_id: str
    original_card_name_zh: str
    original_is_reversed: bool
    original_meaning: str
    clarifier_card_id: str
    clarifier_card_name_zh: str
    clarifier_is_reversed: bool
    clarifier_meaning: str
    interpretation: str


def _card_meaning(card: Card, is_reversed: bool) -> tuple[str, list[str]]:
    if is_reversed:
        return card.reversed_meaning, card.reversed_keywords
    return card.upright_meaning, card.upright_keywords


def interpret_clarifier(
    position: Position,
    original: Card,
    original_reversed: bool,
    clarifier: Card,
    clarifier_reversed: bool,
) -> str:
    orig_meaning, orig_kw = _card_meaning(original, original_reversed)
    clar_meaning, clar_kw = _card_meaning(clarifier, clarifier_reversed)
    orig_orient = "逆位" if original_reversed else "正位"
    clar_orient = "逆位" if clarifier_reversed else "正位"

    return (
        f"【{position.label} · 澄清】\n"
        f"原牌「{original.name_zh}」({orig_orient})：{orig_meaning}\n"
        f"澄清牌「{clarifier.name_zh}」({clar_orient})：{clar_meaning}\n"
        f"组合提示：{position.label}的「{original.name_zh}」因「{clarifier.name_zh}」而需要关注——"
        f"{orig_meaning}；澄清牌进一步指向：{clar_meaning}\n"
        f"关键词：{' · '.join(orig_kw)} → {' · '.join(clar_kw)}"
    )


def build_clarifier_reading(
    clarifier_id: int,
    clarifies_position: int,
    position: Position,
    original_card_id: str,
    original_reversed: bool,
    clarifier_card_id: str,
    clarifier_reversed: bool,
) -> ClarifierReading | None:
    original = get_card(original_card_id)
    clarifier_card = get_card(clarifier_card_id)
    if not original or not clarifier_card:
        return None

    orig_meaning, _ = _card_meaning(original, original_reversed)
    clar_meaning, _ = _card_meaning(clarifier_card, clarifier_reversed)

    return ClarifierReading(
        id=clarifier_id,
        clarifies_position=clarifies_position,
        position_label=position.label,
        position_hint=position.hint,
        original_card_id=original.id,
        original_card_name_zh=original.name_zh,
        original_is_reversed=original_reversed,
        original_meaning=orig_meaning,
        clarifier_card_id=clarifier_card.id,
        clarifier_card_name_zh=clarifier_card.name_zh,
        clarifier_is_reversed=clarifier_reversed,
        clarifier_meaning=clar_meaning,
        interpretation=interpret_clarifier(
            position, original, original_reversed, clarifier_card, clarifier_reversed
        ),
    )
