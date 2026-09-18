from __future__ import annotations

import httpx

from app.database import get_setting
from app.services.clarifier import ClarifierReading
from app.services.interpreter import SpreadAnalysis


def is_ai_configured() -> bool:
    return bool(get_setting("api_key") and get_setting("api_base_url"))


def build_prompt(
    question: str,
    spread_name: str,
    analysis: SpreadAnalysis,
    clarifiers: list[ClarifierReading] | None = None,
) -> str:
    lines = [
        "你是一位经验丰富的塔罗解读师。请基于以下信息，给出深入、温暖且实用的解读。",
        f"\n问题：{question}",
        f"牌阵：{spread_name}",
        "\n各位置牌面：",
    ]
    for pos in analysis.positions:
        orientation = "逆位" if pos.is_reversed else "正位"
        lines.append(
            f"- {pos.position_label}：{pos.card_name_zh}（{orientation}）"
            f" 关键词：{'、'.join(pos.keywords)}"
        )
    lines.append("\n模板解读参考：")
    for pos in analysis.positions:
        lines.append(pos.interpretation)
    if clarifiers:
        lines.append("\n澄清牌（原牌 vs 澄清牌）：")
        for cr in clarifiers:
            orig_orient = "逆位" if cr.original_is_reversed else "正位"
            clar_orient = "逆位" if cr.clarifier_is_reversed else "正位"
            lines.append(
                f"- {cr.position_label}：原牌 {cr.original_card_name_zh}（{orig_orient}）"
                f" → 澄清牌 {cr.clarifier_card_name_zh}（{clar_orient}）"
            )
            lines.append(cr.interpretation)
    if analysis.narrative:
        lines.append("\n整阵叙事：")
        lines.extend(analysis.narrative)
    clarifier_hint = "，并整合澄清牌对原牌的修正" if clarifiers else ""
    lines.append(
        f"\n请综合以上信息，给出：1) 整体概述 2) 各位置深入解读 "
        f"3) 行动建议{clarifier_hint}。语气温暖但不回避挑战，使用中文。"
    )
    return "\n".join(lines)


async def generate_ai_reading(
    question: str,
    spread_name: str,
    analysis: SpreadAnalysis,
    clarifiers: list[ClarifierReading] | None = None,
) -> str:
    api_key = get_setting("api_key")
    api_base = get_setting("api_base_url", "https://api.openai.com/v1")
    model = get_setting("model_name", "gpt-4o-mini")

    if not api_key:
        raise ValueError("未配置 API Key，请前往设置页配置。")

    prompt = build_prompt(question, spread_name, analysis, clarifiers)
    url = f"{api_base.rstrip('/')}/chat/completions"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
