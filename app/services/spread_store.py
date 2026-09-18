from __future__ import annotations

import json
import uuid
from datetime import datetime

from app.database import get_connection
from app.models.spread import Position, Spread
from app.services.layout_presets import build_layout


def _row_to_spread(row) -> Spread:
    positions = [Position(**p) for p in json.loads(row["positions_json"])]
    layout = json.loads(row["layout_json"])
    keys = row.keys()
    scene = row["category"] if "category" in keys else "general"
    return Spread(
        id=row["id"],
        name_zh=row["name_zh"],
        category="custom",
        card_count=row["card_count"],
        description=row["description"] or "",
        positions=positions,
        tips=row["tips"] or "按坑位顺序串联各牌意象，形成完整叙事。",
        layout=layout,
        scene=scene,
    )


def save_custom_spread(
    name_zh: str,
    positions: list[tuple[str, str]],
    description: str = "",
    tips: str = "",
    layout_preset: str = "grid",
    category: str = "general",
) -> str:
    spread_id = f"custom-{uuid.uuid4().hex[:8]}"
    pos_data = [
        {"index": i, "label": label, "hint": hint or f"{label}位置的解读提示"}
        for i, (label, hint) in enumerate(positions)
    ]
    layout = build_layout(layout_preset, len(positions))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO custom_spreads "
            "(id, name_zh, description, category, card_count, positions_json, layout_json, tips, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                spread_id,
                name_zh,
                description,
                category,
                len(positions),
                json.dumps(pos_data, ensure_ascii=False),
                json.dumps(layout, ensure_ascii=False),
                tips,
                now,
            ),
        )
        conn.commit()
        from app.services.card_loader import invalidate_spread_cache

        invalidate_spread_cache()
        return spread_id
    finally:
        conn.close()


def load_custom_spreads() -> list[Spread]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM custom_spreads ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_spread(r) for r in rows]
    finally:
        conn.close()


def get_custom_spread(spread_id: str) -> Spread | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM custom_spreads WHERE id = ?", (spread_id,)
        ).fetchone()
        return _row_to_spread(row) if row else None
    finally:
        conn.close()


def update_custom_spread(
    spread_id: str,
    name_zh: str,
    positions: list[tuple[str, str]],
    description: str = "",
    tips: str = "",
    layout_preset: str = "grid",
    category: str = "general",
) -> bool:
    pos_data = [
        {"index": i, "label": label, "hint": hint or f"{label}位置的解读提示"}
        for i, (label, hint) in enumerate(positions)
    ]
    layout = build_layout(layout_preset, len(positions))

    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE custom_spreads SET "
            "name_zh = ?, description = ?, category = ?, card_count = ?, "
            "positions_json = ?, layout_json = ?, tips = ? "
            "WHERE id = ?",
            (
                name_zh,
                description,
                category,
                len(positions),
                json.dumps(pos_data, ensure_ascii=False),
                json.dumps(layout, ensure_ascii=False),
                tips,
                spread_id,
            ),
        )
        conn.commit()
        from app.services.card_loader import invalidate_spread_cache

        invalidate_spread_cache()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_custom_spread(spread_id: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM custom_spreads WHERE id = ?", (spread_id,))
        conn.commit()
        from app.services.card_loader import invalidate_spread_cache

        invalidate_spread_cache()
        return cur.rowcount > 0
    finally:
        conn.close()


def export_custom_spreads_raw() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM custom_spreads").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def import_custom_spreads_raw(items: list[dict]) -> int:
    conn = get_connection()
    count = 0
    try:
        for item in items:
            conn.execute(
                "INSERT OR REPLACE INTO custom_spreads "
                "(id, name_zh, description, category, card_count, positions_json, layout_json, tips, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item["id"],
                    item["name_zh"],
                    item.get("description", ""),
                    item.get("category", "general"),
                    item["card_count"],
                    item["positions_json"],
                    item["layout_json"],
                    item.get("tips", ""),
                    item.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                ),
            )
            count += 1
        conn.commit()
        from app.services.card_loader import invalidate_spread_cache

        invalidate_spread_cache()
        return count
    finally:
        conn.close()
