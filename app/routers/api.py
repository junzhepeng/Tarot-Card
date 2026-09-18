from __future__ import annotations

from fastapi import APIRouter, HTTPException
import json

from fastapi.responses import Response
from pydantic import BaseModel

from app.services.ai_service import generate_ai_reading, is_ai_configured
from app.services.card_loader import get_card, get_spread, load_cards
from app.services.interpreter import interpret_spread
from app.services.clarifier import build_clarifier_reading
from app.services.backup_service import export_backup
from app.services.exporter import export_reading_markdown
from app.services.reading_store import (
    add_clarifier,
    delete_clarifier,
    get_clarifier_readings,
    get_reading,
    update_ai_summary,
)

router = APIRouter(prefix="/api")


class AIRequest(BaseModel):
    reading_id: int


class ClarifierRequest(BaseModel):
    reading_id: int
    position_index: int
    card_id: str
    is_reversed: bool = False


class ClarifierDeleteRequest(BaseModel):
    clarifier_id: int


@router.get("/spreads/{spread_id}")
async def api_get_spread(spread_id: str):
    spread = get_spread(spread_id)
    if not spread:
        raise HTTPException(404, "牌阵不存在。")
    return {
        "id": spread.id,
        "name_zh": spread.name_zh,
        "description": spread.description,
        "tips": spread.tips,
        "positions": [
            {"index": p.index, "label": p.label, "hint": p.hint}
            for p in spread.positions
        ],
        "layout": spread.layout,
    }


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
            "image_url": c.image_url,
            "number": c.number,
            "search": f"{c.name_zh} {c.name_en} {c.id} {c.number} {c.suit or ''}".lower(),
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

    drawn = [
        (c.position_index, c.card_id, c.is_reversed) for c in record.spread_cards
    ]
    analysis = interpret_spread(spread, drawn)
    clarifiers = get_clarifier_readings(record)

    try:
        summary = await generate_ai_reading(
            record.question, spread.name_zh, analysis, clarifiers
        )
        update_ai_summary(body.reading_id, summary)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(500, f"AI 解读失败：{e}")


def _clarifier_to_dict(reading) -> dict:
    card = get_card(reading.clarifier_card_id)
    original = get_card(reading.original_card_id)
    return {
        "id": reading.id,
        "clarifies_position": reading.clarifies_position,
        "position_label": reading.position_label,
        "original_card_id": reading.original_card_id,
        "original_card_name_zh": reading.original_card_name_zh,
        "original_is_reversed": reading.original_is_reversed,
        "original_image_url": original.image_url if original else "",
        "clarifier_card_id": reading.clarifier_card_id,
        "clarifier_card_name_zh": reading.clarifier_card_name_zh,
        "clarifier_is_reversed": reading.clarifier_is_reversed,
        "clarifier_image_url": card.image_url if card else "",
        "interpretation": reading.interpretation,
    }


@router.post("/clarifier")
async def api_add_clarifier(body: ClarifierRequest):
    record = get_reading(body.reading_id)
    if not record:
        raise HTTPException(404, "占卜记录不存在。")

    spread = get_spread(record.spread_id)
    if not spread:
        raise HTTPException(404, "牌阵不存在。")

    if body.position_index < 0 or body.position_index >= spread.card_count:
        raise HTTPException(400, "无效的坑位索引。")

    spread_card = next(
        (c for c in record.spread_cards if c.position_index == body.position_index),
        None,
    )
    if not spread_card:
        raise HTTPException(400, "该坑位尚未录入牌面。")

    clarifier_card = get_card(body.card_id)
    if not clarifier_card:
        raise HTTPException(400, "无效的牌。")

    clarifier_id = add_clarifier(
        body.reading_id,
        body.position_index,
        body.card_id,
        body.is_reversed,
    )
    position = spread.get_position(body.position_index)
    built = build_clarifier_reading(
        clarifier_id=clarifier_id,
        clarifies_position=body.position_index,
        position=position,
        original_card_id=spread_card.card_id,
        original_reversed=spread_card.is_reversed,
        clarifier_card_id=body.card_id,
        clarifier_reversed=body.is_reversed,
    )
    if not built:
        raise HTTPException(500, "生成澄清解读失败。")

    return {"clarifier": _clarifier_to_dict(built)}


@router.delete("/clarifier")
async def api_delete_clarifier(body: ClarifierDeleteRequest):
    if not delete_clarifier(body.clarifier_id):
        raise HTTPException(404, "澄清牌不存在。")
    return {"ok": True}


@router.get("/reading/{reading_id}/clarifiers")
async def api_list_clarifiers(reading_id: int):
    record = get_reading(reading_id)
    if not record:
        raise HTTPException(404, "占卜记录不存在。")
    readings = get_clarifier_readings(record)
    return {"clarifiers": [_clarifier_to_dict(r) for r in readings]}


@router.get("/backup")
async def api_backup():
    data = export_backup()
    return Response(
        content=json.dumps(data, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="tarot-backup.json"'},
    )


@router.get("/reading/{reading_id}/export.md")
async def api_export_reading(reading_id: int, mode: str = "full"):
    if mode not in ("full", "client"):
        mode = "full"
    markdown = export_reading_markdown(reading_id, mode=mode)
    if not markdown:
        raise HTTPException(404, "占卜记录不存在。")
    filename = (
        f"reading-{reading_id}-client.md"
        if mode == "client"
        else f"reading-{reading_id}.md"
    )
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
