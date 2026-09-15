from __future__ import annotations

from collections import Counter

from app.models.card import Card
from app.services.card_loader import get_card

ELEMENT_MAP = {
    "wands": "火",
    "cups": "水",
    "swords": "风",
    "pentacles": "土",
}


def analyze_patterns(drawn: list[tuple[str, bool]]) -> dict:
    """Analyze drawn cards. Each item is (card_id, is_reversed)."""
    cards: list[Card] = []
    for card_id, _ in drawn:
        card = get_card(card_id)
        if card:
            cards.append(card)

    major = sum(1 for c in cards if c.arcana == "major")
    minor = len(cards) - major
    reversed_count = sum(1 for _, rev in drawn if rev)
    upright_count = len(drawn) - reversed_count

    elements: Counter[str] = Counter()
    for c in cards:
        if c.suit:
            elements[ELEMENT_MAP[c.suit]] += 1
        elif c.element:
            elements[c.element] += 1

    numbers = [c.number for c in cards if c.arcana == "minor" and c.number <= 10]
    number_dupes = [n for n, cnt in Counter(numbers).items() if cnt > 1]

    court_cards = [c.name_zh for c in cards if c.is_court]
    suits = Counter(c.suit for c in cards if c.suit)

    insights: list[str] = []
    if major >= len(cards) // 2 + 1:
        insights.append(f"大阿卡纳占多数（{major}/{len(cards)}），此事具有重要的人生意义，涉及深层转变。")
    if reversed_count > upright_count:
        insights.append(f"逆位牌较多（{reversed_count}/{len(cards)}），能量受阻或需要内省，事情可能尚未成熟。")
    elif upright_count == len(cards):
        insights.append("全部正位，能量流畅，事情按自然方向推进。")

    dominant_suit = suits.most_common(1)
    if dominant_suit and dominant_suit[0][1] >= 2:
        suit_name = {"wands": "权杖（行动/热情）", "cups": "圣杯（情感）",
                     "swords": "宝剑（思维）", "pentacles": "星币（物质）"}
        insights.append(f"「{suit_name[dominant_suit[0][0]]}」花色突出（{dominant_suit[0][1]}张），该领域是核心主题。")

    if number_dupes:
        insights.append(f"重复数字 {', '.join(str(n) for n in number_dupes)}，该数字的能量被强调。")
    if len(court_cards) >= 2:
        insights.append(f"多张宫廷牌（{'、'.join(court_cards)}），涉及具体人物或性格特质。")

    dominant_element = elements.most_common(1)
    if dominant_element and dominant_element[0][1] >= 2:
        insights.append(f"「{dominant_element[0][0]}」元素突出，相关能量主导此次解读。")

    return {
        "major_count": major,
        "minor_count": minor,
        "upright_count": upright_count,
        "reversed_count": reversed_count,
        "elements": dict(elements),
        "court_cards": court_cards,
        "number_duplicates": number_dupes,
        "insights": insights,
    }
