from __future__ import annotations

from dataclasses import dataclass

from app.models.card import Card
from app.models.spread import Position, Spread
from app.services.card_loader import get_card
from app.services.pattern_analyzer import analyze_patterns


@dataclass
class PositionReading:
    position_index: int
    position_label: str
    position_hint: str
    card_id: str
    card_name_zh: str
    card_name_en: str
    is_reversed: bool
    keywords: list[str]
    meaning: str
    interpretation: str


@dataclass
class SpreadAnalysis:
    positions: list[PositionReading]
    patterns: dict
    narrative: list[str]
    spread_tips: str


def interpret_position(position: Position, card: Card, is_reversed: bool) -> PositionReading:
    keywords = card.reversed_keywords if is_reversed else card.upright_keywords
    meaning = card.reversed_meaning if is_reversed else card.upright_meaning
    orientation = "逆位" if is_reversed else "正位"
    interpretation = (
        f"【{position.label}】{position.hint}\n"
        f"抽到「{card.name_zh}」({orientation})：{meaning}\n"
        f"关键词：{' · '.join(keywords)}"
    )
    return PositionReading(
        position_index=position.index,
        position_label=position.label,
        position_hint=position.hint,
        card_id=card.id,
        card_name_zh=card.name_zh,
        card_name_en=card.name_en,
        is_reversed=is_reversed,
        keywords=keywords,
        meaning=meaning,
        interpretation=interpretation,
    )


def _narrative_yes_no(pos: PositionReading) -> list[str]:
    tendency = "倾向于肯定" if not pos.is_reversed else "倾向于否定或暂缓"
    return [
        f"是非牌解读：{tendency}。",
        f"「{pos.card_name_zh}」{'逆位' if pos.is_reversed else '正位'}提示：{pos.meaning}",
        "注意：逆位不一定是「否」，可能意味着需要等待、换种方式，或事情尚未成熟。请结合牌义综合判断。",
    ]


def _narrative_past_present_future(positions: list[PositionReading]) -> list[str]:
    if len(positions) < 3:
        return []
    p, pr, f = positions[0], positions[1], positions[2]
    return [
        f"时间流叙事：过去的「{p.card_name_zh}」塑造了现在的「{pr.card_name_zh}」，"
        f"若延续此路，未来趋向「{f.card_name_zh}」的能量。",
        "关注三张牌之间的花色与主题联系，它们共同讲述一个故事。",
    ]


def _narrative_cross(positions: list[PositionReading]) -> list[str]:
    if len(positions) < 5:
        return []
    situation, challenge, advice, foundation, outcome = positions
    return [
        f"处境：「{situation.card_name_zh}」描述你当前的状态。",
        f"挑战 vs 建议：面对「{challenge.card_name_zh}」的阻碍，"
        f"建议采取「{advice.card_name_zh}」的态度与行动。",
        f"根基：「{foundation.card_name_zh}」揭示深层的驱动力。",
        f"可能结果：若遵循建议，趋向「{outcome.card_name_zh}」的方向。",
    ]


def _narrative_lovers_cross(positions: list[PositionReading]) -> list[str]:
    if len(positions) < 5:
        return []
    you, partner, connection, undercurrent, potential = positions
    return [
        f"你（{you.card_name_zh}）与伴侣（{partner.card_name_zh}）的能量对比，"
        f"关注两者是否互补或存在冲突。",
        f"连接（{connection.card_name_zh}）揭示你们之间的纽带与互动模式。",
        f"暗流（{undercurrent.card_name_zh}）提示未说出口或隐藏的影响。",
        f"潜力（{potential.card_name_zh}）指向关系的长期走向。",
    ]


def _narrative_secret_crush(positions: list[PositionReading]) -> list[str]:
    if len(positions) < 5:
        return []
    guidance = positions[4]
    return [
        f"对方感受（{positions[0].card_name_zh}）与追求时机（{positions[1].card_name_zh}）"
        f"共同描绘当前局面。",
        f"未来潜力（{positions[2].card_name_zh}）与外部因素（{positions[3].card_name_zh}）"
        f"提供背景信息。",
        f"最重要的指引：「{guidance.card_name_zh}」——{guidance.meaning}",
    ]


def _narrative_voice_of_heart(positions: list[PositionReading]) -> list[str]:
    if len(positions) < 8:
        return []
    return [
        f"感情现状（{positions[0].card_name_zh}）与近期趋势（{positions[1].card_name_zh}）"
        f"勾勒整体画面。",
        f"你的内在（{positions[2].card_name_zh}）与外在（{positions[3].card_name_zh}）"
        f"是否存在落差？",
        f"对方想法（{positions[4].card_name_zh}）与期望（{positions[5].card_name_zh}）"
        f"对比你的想法（{positions[6].card_name_zh}），寻找共识与分歧。",
        f"综合建议：「{positions[7].card_name_zh}」——{positions[7].meaning}",
    ]


NARRATIVE_HANDLERS = {
    "yes-no": lambda pos: _narrative_yes_no(pos[0]) if pos else [],
    "past-present-future": _narrative_past_present_future,
    "triad": lambda pos: [
        f"三牌叙事：「{pos[0].card_name_zh}」→「{pos[1].card_name_zh}」→「{pos[2].card_name_zh}」，"
        "自行串联成完整故事。"
    ] if len(pos) >= 3 else [],
    "cross": _narrative_cross,
    "lovers-cross": _narrative_lovers_cross,
    "secret-crush": _narrative_secret_crush,
    "voice-of-heart": _narrative_voice_of_heart,
    "single-card": lambda pos: [
        f"核心洞察：「{pos[0].card_name_zh}」——{pos[0].meaning}"
    ] if pos else [],
}


def interpret_spread(
    spread: Spread,
    drawn: list[tuple[int, str, bool]],
) -> SpreadAnalysis:
    """drawn: list of (position_index, card_id, is_reversed)"""
    position_readings: list[PositionReading] = []
    pattern_input: list[tuple[str, bool]] = []

    for pos_idx, card_id, is_reversed in drawn:
        card = get_card(card_id)
        if not card:
            continue
        position = spread.get_position(pos_idx)
        position_readings.append(interpret_position(position, card, is_reversed))
        pattern_input.append((card_id, is_reversed))

    position_readings.sort(key=lambda r: r.position_index)
    patterns = analyze_patterns(pattern_input)

    handler = NARRATIVE_HANDLERS.get(spread.id, lambda pos: [])
    narrative = handler(position_readings)

    if patterns["insights"]:
        narrative.append("---")
        narrative.extend(patterns["insights"])

    return SpreadAnalysis(
        positions=position_readings,
        patterns=patterns,
        narrative=narrative,
        spread_tips=spread.tips,
    )
