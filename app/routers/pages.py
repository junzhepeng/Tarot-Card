from __future__ import annotations

import json
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.constants import OUTCOME_STATUSES, READING_CATEGORIES
from app.database import get_setting, set_setting
from app.services.ai_service import is_ai_configured
from app.services.backup_service import import_backup
from app.services.card_loader import get_card, get_spread, load_cards, load_spreads
from datetime import date

from app.services.daily_store import (
    delete_daily_entry,
    get_today_entry,
    list_daily_entries,
    save_daily_entry,
)
from app.services.guide_loader import load_guide
from app.services.interpreter import interpret_spread
from app.services.spread_store import delete_custom_spread, save_custom_spread
from app.services.reading_store import (
    add_clarifier,
    delete_clarifier,
    get_clarifier_readings,
    get_reading,
    list_readings,
    save_reading,
    update_notes,
    update_outcome,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["urlencode"] = lambda s: quote(str(s), safe="")

CATEGORY_LABELS = {
    "quick": "快速",
    "classic": "经典",
    "relationship": "感情",
    "custom": "自定义",
}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    spreads = load_spreads()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "spread_count": len(spreads), "card_count": len(load_cards())},
    )


@router.get("/library", response_class=HTMLResponse)
async def library(
    request: Request,
    q: str = "",
    arcana: str = "",
    suit: str = "",
):
    cards = load_cards()
    if q:
        q_lower = q.lower()
        cards = [
            c for c in cards
            if q_lower in c.name_zh.lower()
            or q_lower in c.name_en.lower()
            or q_lower in c.id.lower()
        ]
    if arcana:
        cards = [c for c in cards if c.arcana == arcana]
    if suit:
        cards = [c for c in cards if c.suit == suit]
    return templates.TemplateResponse(
        "library.html",
        {"request": request, "cards": cards, "q": q, "arcana": arcana, "suit": suit},
    )


@router.get("/library/{card_id}", response_class=HTMLResponse)
async def card_detail(request: Request, card_id: str):
    card = get_card(card_id)
    if not card:
        return RedirectResponse("/library", status_code=302)
    return templates.TemplateResponse(
        "card_detail.html", {"request": request, "card": card}
    )


@router.get("/spreads", response_class=HTMLResponse)
async def spreads_page(request: Request, category: str = ""):
    spreads = load_spreads()
    if category:
        spreads = [s for s in spreads if s.category == category]
    return templates.TemplateResponse(
        "spreads.html",
        {
            "request": request,
            "spreads": spreads,
            "category": category,
            "category_labels": CATEGORY_LABELS,
        },
    )


@router.get("/spreads/{spread_id}", response_class=HTMLResponse)
async def spread_detail(request: Request, spread_id: str):
    spread = get_spread(spread_id)
    if not spread:
        return RedirectResponse("/spreads", status_code=302)
    return templates.TemplateResponse(
        "spread_detail.html",
        {
            "request": request,
            "spread": spread,
            "category_labels": CATEGORY_LABELS,
            "is_custom": spread_id.startswith("custom-"),
        },
    )


@router.get("/reading/new", response_class=HTMLResponse)
async def reading_new(
    request: Request,
    step: int = 1,
    spread_id: str = "",
    question: str = "",
):
    spreads = load_spreads()
    cards = load_cards()
    spread = get_spread(spread_id) if spread_id else None

    if step >= 3:
        if not spread:
            return RedirectResponse("/reading/new?step=2", status_code=302)
        if not question.strip():
            return RedirectResponse(
                f"/reading/new?step=1&spread_id={spread_id}", status_code=302
            )

    if step == 2 and not question.strip():
        return RedirectResponse("/reading/new?step=1", status_code=302)

    return templates.TemplateResponse(
        "reading_new.html",
        {
            "request": request,
            "step": step,
            "question": question,
            "spreads": spreads,
            "spread": spread,
            "cards": cards,
            "category_labels": CATEGORY_LABELS,
        },
    )


@router.post("/reading/submit")
async def reading_submit(request: Request):
    form = await request.form()
    question = form.get("question", "")
    spread_id = form.get("spread_id", "")
    spread = get_spread(spread_id)
    if not spread:
        return RedirectResponse("/reading/new", status_code=302)

    drawn = []
    for i in range(spread.card_count):
        card_id = form.get(f"card_{i}")
        is_reversed = form.get(f"reversed_{i}") == "1"
        if card_id:
            drawn.append((i, card_id, is_reversed))

    if not question.strip():
        return RedirectResponse(
            f"/reading/new?step=1&spread_id={spread_id}", status_code=302
        )

    if len(drawn) != spread.card_count:
        q = quote(question)
        return RedirectResponse(
            f"/reading/new?step=3&spread_id={spread_id}&question={q}",
            status_code=302,
        )

    reading_id = save_reading(question, spread_id, drawn)
    return RedirectResponse(f"/reading/{reading_id}", status_code=302)


@router.get("/reading/{reading_id}", response_class=HTMLResponse)
async def reading_result(request: Request, reading_id: int):
    record = get_reading(reading_id)
    if not record:
        return RedirectResponse("/history", status_code=302)

    spread = get_spread(record.spread_id)
    if not spread:
        return RedirectResponse("/history", status_code=302)

    drawn = [
        (c.position_index, c.card_id, c.is_reversed) for c in record.spread_cards
    ]
    analysis = interpret_spread(spread, drawn)
    clarifier_readings = get_clarifier_readings(record)

    cards = load_cards()
    card_map = {c.id: c for c in cards}
    clarifiers_by_position: dict[int, list] = {}
    for cr in clarifier_readings:
        clarifiers_by_position.setdefault(cr.clarifies_position, []).append(cr)

    return templates.TemplateResponse(
        "reading_result.html",
        {
            "request": request,
            "record": record,
            "spread": spread,
            "analysis": analysis,
            "card_map": card_map,
            "cards": cards,
            "clarifiers_by_position": clarifiers_by_position,
            "ai_configured": is_ai_configured(),
            "category_labels": CATEGORY_LABELS,
            "reading_categories": READING_CATEGORIES,
            "outcome_statuses": OUTCOME_STATUSES,
        },
    )


@router.post("/reading/{reading_id}/notes")
async def save_notes(reading_id: int, notes: str = Form("")):
    update_notes(reading_id, notes)
    return RedirectResponse(f"/reading/{reading_id}", status_code=302)


@router.post("/reading/{reading_id}/clarifier")
async def reading_add_clarifier(
    reading_id: int,
    position_index: int = Form(...),
    card_id: str = Form(...),
    is_reversed: str = Form(""),
):
    record = get_reading(reading_id)
    if not record:
        return RedirectResponse("/history", status_code=302)

    spread = get_spread(record.spread_id)
    if not spread or position_index < 0 or position_index >= spread.card_count:
        return RedirectResponse(f"/reading/{reading_id}", status_code=302)

    if not get_card(card_id):
        return RedirectResponse(f"/reading/{reading_id}", status_code=302)

    spread_card = next(
        (c for c in record.spread_cards if c.position_index == position_index),
        None,
    )
    if not spread_card:
        return RedirectResponse(f"/reading/{reading_id}", status_code=302)

    add_clarifier(reading_id, position_index, card_id, is_reversed == "1")
    return RedirectResponse(
        f"/reading/{reading_id}#position-{position_index}", status_code=302
    )


@router.post("/reading/{reading_id}/clarifier/delete")
async def reading_delete_clarifier(
    reading_id: int,
    clarifier_id: int = Form(...),
):
    delete_clarifier(clarifier_id)
    return RedirectResponse(f"/reading/{reading_id}", status_code=302)


@router.post("/reading/{reading_id}/outcome")
async def save_outcome(
    reading_id: int,
    category: str = Form(""),
    outcome_status: str = Form("pending"),
    outcome_notes: str = Form(""),
):
    if outcome_status not in OUTCOME_STATUSES:
        outcome_status = "pending"
    if category not in READING_CATEGORIES:
        category = ""
    update_outcome(reading_id, category, outcome_status, outcome_notes)
    return RedirectResponse(f"/reading/{reading_id}#review", status_code=302)


@router.get("/history", response_class=HTMLResponse)
async def history(
    request: Request,
    q: str = "",
    category: str = "",
    outcome_status: str = "",
):
    readings = list_readings(q=q, category=category, outcome_status=outcome_status)
    spread_map = {s.id: s for s in load_spreads()}
    card_map = {c.id: c for c in load_cards()}
    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "readings": readings,
            "spread_map": spread_map,
            "card_map": card_map,
            "q": q,
            "category": category,
            "outcome_status": outcome_status,
            "reading_categories": READING_CATEGORIES,
            "outcome_statuses": OUTCOME_STATUSES,
        },
    )


@router.get("/daily", response_class=HTMLResponse)
async def daily_page(request: Request):
    today = date.today().isoformat()
    today_entry = get_today_entry()
    entries = list_daily_entries()
    cards = load_cards()
    card_map = {c.id: c for c in cards}
    return templates.TemplateResponse(
        "daily.html",
        {
            "request": request,
            "today": today,
            "today_entry": today_entry,
            "entries": entries,
            "cards": cards,
            "card_map": card_map,
        },
    )


@router.post("/daily")
async def daily_save(
    card_id: str = Form(...),
    is_reversed: str = Form(""),
    notes: str = Form(""),
):
    if not get_card(card_id):
        return RedirectResponse("/daily", status_code=302)
    save_daily_entry(card_id, is_reversed == "1", notes)
    return RedirectResponse("/daily", status_code=302)


@router.post("/daily/{entry_id}/delete")
async def daily_delete(entry_id: int):
    delete_daily_entry(entry_id)
    return RedirectResponse("/daily", status_code=302)


@router.get("/guide", response_class=HTMLResponse)
async def guide_page(request: Request):
    return templates.TemplateResponse(
        "guide.html",
        {"request": request, "guide": load_guide()},
    )


@router.get("/compare", response_class=HTMLResponse)
async def compare_page(request: Request, a: int = 0, b: int = 0):
    readings = list_readings()
    card_map = {c.id: c for c in load_cards()}
    reading_a = get_reading(a) if a else None
    reading_b = get_reading(b) if b else None
    spread_a = get_spread(reading_a.spread_id) if reading_a else None
    spread_b = get_spread(reading_b.spread_id) if reading_b else None

    common_cards: list[str] = []
    if reading_a and reading_b:
        names_a = {
            card_map[c.card_id].name_zh
            for c in reading_a.spread_cards
            if card_map.get(c.card_id)
        }
        names_b = {
            card_map[c.card_id].name_zh
            for c in reading_b.spread_cards
            if card_map.get(c.card_id)
        }
        common_cards = sorted(names_a & names_b)

    return templates.TemplateResponse(
        "compare.html",
        {
            "request": request,
            "readings": readings,
            "reading_a": reading_a,
            "reading_b": reading_b,
            "spread_a": spread_a,
            "spread_b": spread_b,
            "card_map": card_map,
            "common_cards": common_cards,
        },
    )


@router.get("/spreads/builder", response_class=HTMLResponse)
async def spread_builder_page(request: Request, error: str = ""):
    return templates.TemplateResponse(
        "spread_builder.html",
        {"request": request, "error": error},
    )


@router.post("/spreads/builder")
async def spread_builder_save(request: Request):
    form = await request.form()
    name_zh = str(form.get("name_zh", "")).strip()
    description = str(form.get("description", "")).strip()
    tips = str(form.get("tips", "")).strip()
    labels = form.getlist("label")
    hints = form.getlist("hint")

    positions = [
        (str(l).strip(), str(h).strip())
        for l, h in zip(labels, hints)
        if str(l).strip()
    ]
    if not name_zh or len(positions) < 2:
        return RedirectResponse("/spreads/builder?error=1", status_code=302)

    spread_id = save_custom_spread(name_zh, positions, description, tips)
    return RedirectResponse(f"/spreads/{spread_id}", status_code=302)


@router.post("/spreads/{spread_id}/delete")
async def spread_delete(spread_id: str):
    if spread_id.startswith("custom-"):
        delete_custom_spread(spread_id)
    return RedirectResponse("/spreads?category=custom", status_code=302)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, restored: str = "", restore_error: str = ""):
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "api_base_url": get_setting("api_base_url", "https://api.openai.com/v1"),
            "api_key": get_setting("api_key"),
            "model_name": get_setting("model_name", "gpt-4o-mini"),
            "restored": restored,
            "restore_error": restore_error,
        },
    )


@router.post("/settings")
async def settings_save(
    api_base_url: str = Form("https://api.openai.com/v1"),
    api_key: str = Form(""),
    model_name: str = Form("gpt-4o-mini"),
):
    set_setting("api_base_url", api_base_url)
    set_setting("api_key", api_key)
    set_setting("model_name", model_name)
    return RedirectResponse("/settings", status_code=302)


@router.post("/settings/restore")
async def settings_restore(file: UploadFile = File(...)):
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
        result = import_backup(data)
        total = result["readings"] + result["custom_spreads"] + result.get("daily_cards", 0)
        return RedirectResponse(f"/settings?restored={total}", status_code=302)
    except Exception:
        return RedirectResponse("/settings?restore_error=1", status_code=302)
