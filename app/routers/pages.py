from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_setting, set_setting
from app.services.ai_service import is_ai_configured
from app.services.card_loader import get_card, get_spread, load_cards, load_spreads
from app.services.interpreter import interpret_spread
from app.services.reading_store import get_reading, list_readings, save_reading, update_notes

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["urlencode"] = lambda s: quote(str(s), safe="")

CATEGORY_LABELS = {"quick": "快速", "classic": "经典", "relationship": "感情"}


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

    if len(drawn) != spread.card_count:
        return RedirectResponse(
            f"/reading/new?step=3&spread_id={spread_id}", status_code=302
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

    drawn = [(c.position_index, c.card_id, c.is_reversed) for c in record.cards]
    analysis = interpret_spread(spread, drawn)

    return templates.TemplateResponse(
        "reading_result.html",
        {
            "request": request,
            "record": record,
            "spread": spread,
            "analysis": analysis,
            "ai_configured": is_ai_configured(),
            "category_labels": CATEGORY_LABELS,
        },
    )


@router.post("/reading/{reading_id}/notes")
async def save_notes(reading_id: int, notes: str = Form("")):
    update_notes(reading_id, notes)
    return RedirectResponse(f"/reading/{reading_id}", status_code=302)


@router.get("/history", response_class=HTMLResponse)
async def history(request: Request):
    readings = list_readings()
    spread_map = {s.id: s for s in load_spreads()}
    card_map = {c.id: c for c in load_cards()}
    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "readings": readings,
            "spread_map": spread_map,
            "card_map": card_map,
        },
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "api_base_url": get_setting("api_base_url", "https://api.openai.com/v1"),
            "api_key": get_setting("api_key"),
            "model_name": get_setting("model_name", "gpt-4o-mini"),
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
