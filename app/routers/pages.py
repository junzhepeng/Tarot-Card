from __future__ import annotations

import json
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.constants import OUTCOME_STATUSES, READING_CATEGORIES, READING_TAGS
from app.database import get_setting, set_setting
from app.services.ai_service import is_ai_configured
from app.services.backup_service import import_backup
from app.services.card_loader import get_card, get_spread, load_cards, load_spreads
from datetime import date

from app.services.daily_store import (
    delete_daily_entry,
    get_daily_entry,
    get_today_entry,
    list_daily_entries,
    save_daily_entry,
)
from app.services.guide_loader import load_guide
from app.services.insights_service import get_card_frequencies, get_insights_overview
from app.services.interpreter import interpret_spread
from app.services.layout_presets import LAYOUT_PRESETS
from app.services.spread_store import (
    delete_custom_spread,
    get_custom_spread,
    save_custom_spread,
    update_custom_spread,
)
from app.services.reading_store import (
    add_clarifier,
    delete_clarifier,
    delete_reading,
    delete_readings,
    get_clarifier_readings,
    get_reading,
    list_follow_ups,
    count_due_reviews,
    list_querents,
    list_readings,
    save_reading,
    update_final_summary,
    update_first_impression,
    update_notes,
    update_outcome,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["urlencode"] = lambda s: quote(str(s), safe="")
templates.env.globals["READING_TAGS"] = READING_TAGS
templates.env.globals["READING_CATEGORIES"] = READING_CATEGORIES
templates.env.globals["OUTCOME_STATUSES"] = OUTCOME_STATUSES

CATEGORY_LABELS = {
    "quick": "快速",
    "classic": "经典",
    "relationship": "感情",
    "custom": "自定义",
}

SPREAD_SCENE_LABELS = {
    "general": "综合",
    "relationship": "感情",
    "career": "事业",
    "spiritual": "灵性",
}


def _parse_spread_form(form) -> tuple[str, str, str, str, str, list[tuple[str, str]]]:
    name_zh = str(form.get("name_zh", "")).strip()
    description = str(form.get("description", "")).strip()
    tips = str(form.get("tips", "")).strip()
    layout_preset = str(form.get("layout_preset", "grid")).strip()
    scene = str(form.get("scene", "general")).strip()
    labels = form.getlist("label")
    hints = form.getlist("hint")

    if scene not in SPREAD_SCENE_LABELS:
        scene = "general"
    if layout_preset not in LAYOUT_PRESETS:
        layout_preset = "grid"

    positions = [
        (str(l).strip(), str(h).strip())
        for l, h in zip(labels, hints)
        if str(l).strip()
    ]
    return name_zh, description, tips, layout_preset, scene, positions


def _validate_spread_form(name_zh: str, positions: list, layout_preset: str) -> str | None:
    if not name_zh:
        return "1"
    preset = LAYOUT_PRESETS[layout_preset]
    if len(positions) < preset["min_cards"]:
        return "1"
    if len(positions) > preset["max_cards"]:
        return "2"
    return None


def _parse_tags_param(tags: str) -> list[str]:
    if not tags:
        return []
    return [t.strip() for t in tags.split(",") if t.strip() in READING_TAGS]


def _tags_to_param(tags: list[str]) -> str:
    return ",".join(tags)


def _reading_meta_query(
    querent: str = "",
    tags: str = "",
    parent_id: int = 0,
    follow_up_note: str = "",
    daily_id: int = 0,
    card_id: str = "",
    is_reversed: str = "",
) -> str:
    parts = []
    if querent:
        parts.append(f"querent={quote(querent)}")
    if tags:
        parts.append(f"tags={quote(tags)}")
    if parent_id:
        parts.append(f"parent_id={parent_id}")
    if follow_up_note:
        parts.append(f"follow_up_note={quote(follow_up_note)}")
    if daily_id:
        parts.append(f"daily_id={daily_id}")
    if card_id:
        parts.append(f"card_id={quote(card_id)}")
    if is_reversed:
        parts.append(f"is_reversed={is_reversed}")
    return "&".join(parts)


def _spread_to_edit_data(spread) -> dict:
    return {
        "name_zh": spread.name_zh,
        "description": spread.description,
        "tips": spread.tips,
        "scene": spread.scene or "general",
        "layout_preset": spread.layout.get("preset", "grid"),
        "positions": [{"label": p.label, "hint": p.hint} for p in spread.positions],
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


@router.get("/spreads/builder", response_class=HTMLResponse)
async def spread_builder_page(request: Request, error: str = "", template: str = ""):
    return templates.TemplateResponse(
        "spread_builder.html",
        {
            "request": request,
            "error": error,
            "template_id": template,
            "edit_spread_id": "",
            "edit_data": None,
            "layout_presets": LAYOUT_PRESETS,
            "scene_labels": SPREAD_SCENE_LABELS,
        },
    )


@router.post("/spreads/builder")
async def spread_builder_save(request: Request):
    form = await request.form()
    name_zh, description, tips, layout_preset, scene, positions = _parse_spread_form(form)
    error = _validate_spread_form(name_zh, positions, layout_preset)
    if error:
        return RedirectResponse(f"/spreads/builder?error={error}", status_code=302)

    spread_id = save_custom_spread(
        name_zh,
        positions,
        description,
        tips,
        layout_preset=layout_preset,
        category=scene,
    )
    return RedirectResponse(f"/spreads/{spread_id}", status_code=302)


@router.get("/spreads/{spread_id}/edit", response_class=HTMLResponse)
async def spread_edit_page(request: Request, spread_id: str, error: str = ""):
    if not spread_id.startswith("custom-"):
        return RedirectResponse(f"/spreads/{spread_id}", status_code=302)
    spread = get_custom_spread(spread_id)
    if not spread:
        return RedirectResponse("/spreads?category=custom", status_code=302)
    return templates.TemplateResponse(
        "spread_builder.html",
        {
            "request": request,
            "error": error,
            "template_id": "",
            "edit_spread_id": spread_id,
            "edit_data": _spread_to_edit_data(spread),
            "layout_presets": LAYOUT_PRESETS,
            "scene_labels": SPREAD_SCENE_LABELS,
        },
    )


@router.post("/spreads/{spread_id}/edit")
async def spread_edit_save(request: Request, spread_id: str):
    if not spread_id.startswith("custom-"):
        return RedirectResponse("/spreads", status_code=302)
    form = await request.form()
    name_zh, description, tips, layout_preset, scene, positions = _parse_spread_form(form)
    error = _validate_spread_form(name_zh, positions, layout_preset)
    if error:
        return RedirectResponse(f"/spreads/{spread_id}/edit?error={error}", status_code=302)

    if not update_custom_spread(
        spread_id,
        name_zh,
        positions,
        description,
        tips,
        layout_preset=layout_preset,
        category=scene,
    ):
        return RedirectResponse("/spreads?category=custom", status_code=302)
    return RedirectResponse(f"/spreads/{spread_id}", status_code=302)


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
            "scene_labels": SPREAD_SCENE_LABELS,
            "is_custom": spread_id.startswith("custom-"),
        },
    )


@router.get("/reading/new", response_class=HTMLResponse)
async def reading_new(
    request: Request,
    step: int = 1,
    spread_id: str = "",
    question: str = "",
    querent: str = "",
    tags: str = "",
    parent_id: int = 0,
    follow_up_note: str = "",
    daily_id: int = 0,
    card_id: str = "",
    is_reversed: str = "",
    error: str = "",
):
    spreads = load_spreads()
    cards = load_cards()
    parent_reading = get_reading(parent_id) if parent_id else None
    query_tag_list = request.query_params.getlist("tags")
    if query_tag_list:
        selected_tags = [t for t in query_tag_list if t in READING_TAGS]
        tags = _tags_to_param(selected_tags)
    else:
        selected_tags = _parse_tags_param(tags)

    if parent_reading and step == 1 and not querent.strip():
        querent = parent_reading.querent or ""
        if not selected_tags and parent_reading.tags:
            selected_tags = parent_reading.tags
            tags = _tags_to_param(selected_tags)

    daily_entry = get_daily_entry(daily_id) if daily_id else None
    prefill_card_id = card_id
    prefill_reversed = is_reversed == "1"
    if daily_entry:
        if not prefill_card_id:
            prefill_card_id = daily_entry.card_id
        if not is_reversed:
            prefill_reversed = daily_entry.is_reversed
        if step >= 3 and not question.strip():
            question = f"今日指引（{daily_entry.entry_date}）"
        if step >= 3 and not spread_id:
            spread_id = "single-card"

    spread = get_spread(spread_id) if spread_id else None

    meta_q = _reading_meta_query(
        querent,
        tags,
        parent_id,
        follow_up_note,
        daily_id,
        prefill_card_id,
        "1" if prefill_reversed else "",
    )

    if step >= 2 and not querent.strip():
        return RedirectResponse("/reading/new?step=1&error=querent", status_code=302)

    if step >= 3:
        if not spread:
            return RedirectResponse(f"/reading/new?step=2&{meta_q}", status_code=302)
        if not question.strip():
            url = f"/reading/new?step=1&spread_id={spread_id}"
            if meta_q:
                url += f"&{meta_q}"
            return RedirectResponse(url, status_code=302)

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
            "reading_tags": READING_TAGS,
            "querent": querent,
            "selected_tags": selected_tags,
            "tags_param": tags,
            "parent_id": parent_id,
            "parent_reading": parent_reading,
            "follow_up_note": follow_up_note,
            "querent_options": list_querents(),
            "meta_query": meta_q,
            "daily_id": daily_id,
            "daily_entry": daily_entry,
            "prefill_card_id": prefill_card_id,
            "prefill_reversed": prefill_reversed,
            "error": error,
        },
    )


@router.post("/reading/submit")
async def reading_submit(request: Request):
    form = await request.form()
    question = str(form.get("question", ""))
    spread_id = str(form.get("spread_id", ""))
    spread = get_spread(spread_id)
    if not spread:
        return RedirectResponse("/reading/new", status_code=302)

    drawn = []
    for i in range(spread.card_count):
        card_id = form.get(f"card_{i}")
        is_reversed = form.get(f"reversed_{i}") == "1"
        if card_id:
            drawn.append((i, card_id, is_reversed))

    querent = str(form.get("querent", "")).strip()
    if not querent:
        q = quote(question)
        return RedirectResponse(
            f"/reading/new?step=3&spread_id={spread_id}&question={q}&error=querent",
            status_code=302,
        )
    tag_list = [t for t in form.getlist("tags") if t in READING_TAGS]
    parent_raw = str(form.get("parent_reading_id", "")).strip()
    parent_reading_id = int(parent_raw) if parent_raw.isdigit() else None
    follow_up_note = str(form.get("follow_up_note", "")).strip()
    daily_raw = str(form.get("daily_entry_id", "")).strip()
    daily_entry_id = int(daily_raw) if daily_raw.isdigit() else None

    if not question.strip():
        return RedirectResponse(
            f"/reading/new?step=1&spread_id={spread_id}", status_code=302
        )

    if len(drawn) != spread.card_count:
        q = quote(question)
        meta = _reading_meta_query(
            querent,
            _tags_to_param(tag_list),
            parent_reading_id or 0,
            follow_up_note,
            daily_entry_id or 0,
        )
        url = f"/reading/new?step=3&spread_id={spread_id}&question={q}"
        if meta:
            url += f"&{meta}"
        return RedirectResponse(url, status_code=302)

    reading_id = save_reading(
        question,
        spread_id,
        drawn,
        querent=querent,
        tags=tag_list,
        parent_reading_id=parent_reading_id,
        follow_up_note=follow_up_note,
        daily_entry_id=daily_entry_id,
    )
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

    parent_reading = (
        get_reading(record.parent_reading_id) if record.parent_reading_id else None
    )
    follow_ups = list_follow_ups(reading_id)

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
            "reading_tags": READING_TAGS,
            "outcome_statuses": OUTCOME_STATUSES,
            "parent_reading": parent_reading,
            "follow_ups": follow_ups,
            "today": date.today().isoformat(),
        },
    )


@router.post("/reading/{reading_id}/notes")
async def save_notes(reading_id: int, notes: str = Form("")):
    update_notes(reading_id, notes)
    return RedirectResponse(f"/reading/{reading_id}#layered-notes", status_code=302)


@router.post("/reading/{reading_id}/first-impression")
async def save_first_impression(
    reading_id: int, first_impression: str = Form("")
):
    update_first_impression(reading_id, first_impression)
    return RedirectResponse(f"/reading/{reading_id}#layered-notes", status_code=302)


@router.post("/reading/{reading_id}/final-summary")
async def save_final_summary(reading_id: int, final_summary: str = Form("")):
    update_final_summary(reading_id, final_summary)
    return RedirectResponse(f"/reading/{reading_id}#layered-notes", status_code=302)


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


@router.post("/reading/{reading_id}/delete")
async def reading_delete(reading_id: int):
    delete_reading(reading_id)
    return RedirectResponse("/history", status_code=302)


@router.post("/history/delete")
async def history_bulk_delete(request: Request):
    form = await request.form()
    ids = [int(x) for x in form.getlist("reading_id") if str(x).isdigit()]
    if ids:
        delete_readings(ids)
    return RedirectResponse("/history", status_code=302)


@router.post("/reading/{reading_id}/outcome")
async def save_outcome(
    reading_id: int,
    category: str = Form(""),
    outcome_status: str = Form("pending"),
    outcome_notes: str = Form(""),
    review_due_at: str = Form(""),
):
    if outcome_status not in OUTCOME_STATUSES:
        outcome_status = "pending"
    if category not in READING_CATEGORIES:
        category = ""
    due = review_due_at.strip() or None
    update_outcome(reading_id, category, outcome_status, outcome_notes, due)
    return RedirectResponse(f"/reading/{reading_id}#review", status_code=302)


@router.get("/history", response_class=HTMLResponse)
async def history(
    request: Request,
    q: str = "",
    category: str = "",
    outcome_status: str = "",
    querent: str = "",
    due: str = "",
):
    readings = list_readings(
        q=q,
        category=category,
        outcome_status=outcome_status,
        querent=querent,
        due=due,
    )
    spread_map = {s.id: s for s in load_spreads()}
    card_map = {c.id: c for c in load_cards()}
    parent_ids = {r.parent_reading_id for r in readings if r.parent_reading_id}
    parent_map = {}
    for pid in parent_ids:
        p = get_reading(pid)
        if p:
            parent_map[pid] = p
    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "readings": readings,
            "spread_map": spread_map,
            "card_map": card_map,
            "parent_map": parent_map,
            "q": q,
            "category": category,
            "outcome_status": outcome_status,
            "querent": querent,
            "due": due,
            "due_count": count_due_reviews(),
            "today": date.today().isoformat(),
            "querent_options": list_querents(),
            "reading_categories": READING_CATEGORIES,
            "reading_tags": READING_TAGS,
            "outcome_statuses": OUTCOME_STATUSES,
        },
    )


@router.get("/insights", response_class=HTMLResponse)
async def insights_page(request: Request, querent: str = ""):
    overview = get_insights_overview(querent)
    frequencies = get_card_frequencies(querent=querent, limit=20)
    card_map = {c.id: c for c in load_cards()}
    return templates.TemplateResponse(
        "insights.html",
        {
            "request": request,
            "overview": overview,
            "frequencies": frequencies,
            "card_map": card_map,
            "querent": querent,
            "querent_options": list_querents(),
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

    same_spread = False
    position_rows: list[dict] = []
    common_anywhere: list[dict] = []
    common_same_position: list[dict] = []

    if reading_a and reading_b:
        map_a = {c.position_index: c for c in reading_a.spread_cards}
        map_b = {c.position_index: c for c in reading_b.spread_cards}
        same_spread = (
            reading_a.spread_id == reading_b.spread_id
            and spread_a is not None
            and spread_b is not None
        )

        if same_spread:
            for pos in spread_a.positions:
                ca = map_a.get(pos.index)
                cb = map_b.get(pos.index)
                same_card = bool(ca and cb and ca.card_id == cb.card_id)
                orient_flip = bool(
                    same_card and ca and cb and ca.is_reversed != cb.is_reversed
                )
                row = {
                    "position_index": pos.index,
                    "label": pos.label,
                    "card_a": ca,
                    "card_b": cb,
                    "same_card": same_card,
                    "orient_flip": orient_flip,
                }
                position_rows.append(row)
                if same_card:
                    card = card_map.get(ca.card_id)
                    common_same_position.append(
                        {
                            "name_zh": card.name_zh if card else ca.card_id,
                            "label": pos.label,
                            "orient_flip": orient_flip,
                        }
                    )
        else:
            max_idx = max(
                max((c.position_index for c in reading_a.spread_cards), default=-1),
                max((c.position_index for c in reading_b.spread_cards), default=-1),
            )
            for idx in range(max_idx + 1):
                ca = map_a.get(idx)
                cb = map_b.get(idx)
                label_a = (
                    spread_a.positions[idx].label
                    if spread_a and idx < len(spread_a.positions)
                    else f"位置 {idx + 1}"
                )
                label_b = (
                    spread_b.positions[idx].label
                    if spread_b and idx < len(spread_b.positions)
                    else f"位置 {idx + 1}"
                )
                label = label_a if label_a == label_b else f"{label_a} / {label_b}"
                same_card = bool(ca and cb and ca.card_id == cb.card_id)
                position_rows.append(
                    {
                        "position_index": idx,
                        "label": label,
                        "card_a": ca,
                        "card_b": cb,
                        "same_card": same_card,
                        "orient_flip": bool(
                            same_card and ca and cb and ca.is_reversed != cb.is_reversed
                        ),
                    }
                )

        ids_a = {c.card_id for c in reading_a.spread_cards}
        ids_b = {c.card_id for c in reading_b.spread_cards}
        for card_id in sorted(ids_a & ids_b):
            card = card_map.get(card_id)
            common_anywhere.append(
                {
                    "card_id": card_id,
                    "name_zh": card.name_zh if card else card_id,
                }
            )

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
            "same_spread": same_spread,
            "position_rows": position_rows,
            "common_anywhere": common_anywhere,
            "common_same_position": common_same_position,
        },
    )


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
