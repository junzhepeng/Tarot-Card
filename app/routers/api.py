from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.ai_service import generate_ai_reading, is_ai_configured
from app.services.card_loader import get_spread, load_cards
from app.services.interpreter import interpret_spread
from app.services.reading_store import get_reading, update_ai_summary

router = APIRouter(prefix="/api")


class AIRequest(BaseModel):
    reading_id: int


@router.get("/cards")
async def api_cards():
    cards = load_cards()
    return [
        {
            "id": c.id,
            "name_zh": c.name_zh,
            "name_en": c.name_en,
            "arcana": c.arcana,
            "suit": c.suit,
        }
        for c in cards
    ]


@router.post("/ai-reading")
async def api_ai_reading(body: AIRequest):
    if not is_ai_configured():
        raise HTTPException(400, "未配置 AI API，请前往设置页配置。")

    record = get_reading(body.reading_id)
    if not record:
        raise HTTPException(404, "占卜记录不存在。")

    spread = get_spread(record.spread_id)
    if not spread:
        raise HTTPException(404, "牌阵不存在。")

    drawn = [(c.position_index, c.card_id, c.is_reversed) for c in record.cards]
    analysis = interpret_spread(spread, drawn)

    try:
        summary = await generate_ai_reading(record.question, spread.name_zh, analysis)
        update_ai_summary(body.reading_id, summary)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(500, f"AI 解读失败：{e}")
