from __future__ import annotations

import json
from datetime import datetime

from app.database import get_connection, get_setting, set_setting
from app.services.daily_store import export_daily_raw, import_daily_raw
from app.services.reading_store import get_reading, list_readings
from app.services.spread_store import export_custom_spreads_raw, import_custom_spreads_raw

BACKUP_VERSION = 1


def export_backup() -> dict:
    readings = list_readings()
    reading_data = []
    for r in readings:
        full = get_reading(r.id)
        if not full:
            continue
        reading_data.append(
            {
                "id": full.id,
                "question": full.question,
                "spread_id": full.spread_id,
                "created_at": full.created_at,
                "notes": full.notes,
                "ai_summary": full.ai_summary,
                "category": full.category,
                "outcome_status": full.outcome_status,
                "outcome_notes": full.outcome_notes,
                "reviewed_at": full.reviewed_at,
                "cards": [
                    {
                        "position_index": c.position_index,
                        "card_id": c.card_id,
                        "is_reversed": c.is_reversed,
                        "card_type": c.card_type,
                        "clarifies_position": c.clarifies_position,
                    }
                    for c in full.cards
                ],
            }
        )

    conn = get_connection()
    try:
        settings_rows = conn.execute("SELECT key, value FROM settings").fetchall()
        settings = {r["key"]: r["value"] for r in settings_rows}
    finally:
        conn.close()

    return {
        "version": BACKUP_VERSION,
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "readings": reading_data,
        "settings": settings,
        "custom_spreads": export_custom_spreads_raw(),
        "daily_cards": export_daily_raw(),
    }


def import_backup(data: dict) -> dict:
    if data.get("version") != BACKUP_VERSION:
        raise ValueError("不支持的备份版本。")

    conn = get_connection()
    imported_readings = 0
    try:
        for item in data.get("readings", []):
            existing = conn.execute(
                "SELECT id FROM readings WHERE id = ?", (item["id"],)
            ).fetchone()
            if existing:
                continue

            conn.execute(
                "INSERT INTO readings "
                "(id, question, spread_id, created_at, notes, ai_summary, "
                "category, outcome_status, outcome_notes, reviewed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item["id"],
                    item["question"],
                    item["spread_id"],
                    item["created_at"],
                    item.get("notes", ""),
                    item.get("ai_summary"),
                    item.get("category", ""),
                    item.get("outcome_status", "pending"),
                    item.get("outcome_notes", ""),
                    item.get("reviewed_at"),
                ),
            )
            for card in item.get("cards", []):
                conn.execute(
                    "INSERT INTO reading_cards "
                    "(reading_id, position_index, card_id, is_reversed, card_type, clarifies_position) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        item["id"],
                        card["position_index"],
                        card["card_id"],
                        int(card["is_reversed"]),
                        card.get("card_type", "spread"),
                        card.get("clarifies_position"),
                    ),
                )
            imported_readings += 1

        for key, value in data.get("settings", {}).items():
            set_setting(key, value)

        conn.commit()
    finally:
        conn.close()

    imported_spreads = import_custom_spreads_raw(data.get("custom_spreads", []))
    imported_daily = import_daily_raw(data.get("daily_cards", []))

    return {
        "readings": imported_readings,
        "custom_spreads": imported_spreads,
        "daily_cards": imported_daily,
    }
