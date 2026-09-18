from __future__ import annotations

import json
from datetime import datetime

from app.constants import READING_TAGS
from app.database import get_connection
from app.models.reading import DrawnCard, ReadingRecord
from app.services.card_loader import get_spread
from app.services.clarifier import ClarifierReading, build_clarifier_reading


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        tags = json.loads(raw)
        if isinstance(tags, list):
            return [t for t in tags if t in READING_TAGS]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _row_to_drawn_card(row) -> DrawnCard:
    return DrawnCard(
        id=row["id"],
        position_index=row["position_index"],
        card_id=row["card_id"],
        is_reversed=bool(row["is_reversed"]),
        card_type=row["card_type"] if "card_type" in row.keys() else "spread",
        clarifies_position=row["clarifies_position"]
        if "clarifies_position" in row.keys()
        else None,
    )


def _row_to_record(row, cards: list[DrawnCard]) -> ReadingRecord:
    keys = row.keys()
    parent_id = row["parent_reading_id"] if "parent_reading_id" in keys else None
    return ReadingRecord(
        id=row["id"],
        question=row["question"],
        spread_id=row["spread_id"],
        created_at=row["created_at"],
        notes=row["notes"] or "",
        ai_summary=row["ai_summary"],
        cards=cards,
        category=row["category"] if "category" in keys else "",
        outcome_status=row["outcome_status"] if "outcome_status" in keys else "pending",
        outcome_notes=row["outcome_notes"] if "outcome_notes" in keys else "",
        reviewed_at=row["reviewed_at"] if "reviewed_at" in keys else None,
        review_due_at=row["review_due_at"] if "review_due_at" in keys else None,
        querent=row["querent"] if "querent" in keys else "",
        tags=_parse_tags(row["tags"] if "tags" in keys else "[]"),
        parent_reading_id=parent_id,
        follow_up_note=row["follow_up_note"] if "follow_up_note" in keys else "",
        first_impression=row["first_impression"] if "first_impression" in keys else "",
        final_summary=row["final_summary"] if "final_summary" in keys else "",
        daily_entry_id=row["daily_entry_id"] if "daily_entry_id" in keys else None,
    )


def _load_cards_for_reading(conn, reading_id: int) -> list[DrawnCard]:
    card_rows = conn.execute(
        "SELECT id, position_index, card_id, is_reversed, card_type, clarifies_position "
        "FROM reading_cards WHERE reading_id = ? "
        "ORDER BY card_type, clarifies_position, id",
        (reading_id,),
    ).fetchall()
    return [_row_to_drawn_card(r) for r in card_rows]


def _normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    return [t for t in tags if t in READING_TAGS]


def save_reading(
    question: str,
    spread_id: str,
    cards: list[tuple[int, str, bool]],
    notes: str = "",
    ai_summary: str | None = None,
    querent: str = "",
    tags: list[str] | None = None,
    parent_reading_id: int | None = None,
    follow_up_note: str = "",
    daily_entry_id: int | None = None,
) -> int:
    conn = get_connection()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tag_list = _normalize_tags(tags)
        cur = conn.execute(
            "INSERT INTO readings "
            "(question, spread_id, created_at, notes, ai_summary, querent, tags, "
            "parent_reading_id, follow_up_note, daily_entry_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                question,
                spread_id,
                now,
                notes,
                ai_summary,
                querent.strip(),
                json.dumps(tag_list, ensure_ascii=False),
                parent_reading_id,
                follow_up_note or "",
                daily_entry_id,
            ),
        )
        reading_id = cur.lastrowid
        for pos_idx, card_id, is_reversed in cards:
            conn.execute(
                "INSERT INTO reading_cards "
                "(reading_id, position_index, card_id, is_reversed, card_type) "
                "VALUES (?, ?, ?, ?, 'spread')",
                (reading_id, pos_idx, card_id, int(is_reversed)),
            )
        conn.commit()
        return reading_id
    finally:
        conn.close()


def get_reading(reading_id: int) -> ReadingRecord | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM readings WHERE id = ?", (reading_id,)).fetchone()
        if not row:
            return None
        cards = _load_cards_for_reading(conn, reading_id)
        return _row_to_record(row, cards)
    finally:
        conn.close()


def list_readings(
    q: str = "",
    category: str = "",
    outcome_status: str = "",
    querent: str = "",
    due: str = "",
) -> list[ReadingRecord]:
    conn = get_connection()
    try:
        sql = "SELECT * FROM readings WHERE 1=1"
        params: list = []

        if q.strip():
            sql += " AND question LIKE ?"
            params.append(f"%{q.strip()}%")
        if category:
            sql += " AND category = ?"
            params.append(category)
        if outcome_status:
            sql += " AND outcome_status = ?"
            params.append(outcome_status)
        if querent.strip():
            sql += " AND querent = ?"
            params.append(querent.strip())
        if due == "overdue":
            today = datetime.now().strftime("%Y-%m-%d")
            sql += (
                " AND review_due_at IS NOT NULL AND review_due_at != ''"
                " AND review_due_at <= ?"
            )
            params.append(today)

        sql += " ORDER BY created_at DESC"
        rows = conn.execute(sql, params).fetchall()

        results = []
        for row in rows:
            cards = _load_cards_for_reading(conn, row["id"])
            results.append(_row_to_record(row, cards))
        return results
    finally:
        conn.close()


def list_querents(limit: int = 20) -> list[str]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT querent FROM readings "
            "WHERE querent != '' ORDER BY querent LIMIT ?",
            (limit,),
        ).fetchall()
        return [r["querent"] for r in rows if r["querent"]]
    finally:
        conn.close()


def list_follow_ups(parent_reading_id: int) -> list[ReadingRecord]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM readings WHERE parent_reading_id = ? ORDER BY created_at ASC",
            (parent_reading_id,),
        ).fetchall()
        results = []
        for row in rows:
            cards = _load_cards_for_reading(conn, row["id"])
            results.append(_row_to_record(row, cards))
        return results
    finally:
        conn.close()


def add_clarifier(
    reading_id: int,
    clarifies_position: int,
    card_id: str,
    is_reversed: bool = False,
) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO reading_cards "
            "(reading_id, position_index, card_id, is_reversed, card_type, clarifies_position) "
            "VALUES (?, ?, ?, ?, 'clarifier', ?)",
            (reading_id, clarifies_position, card_id, int(is_reversed), clarifies_position),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def delete_clarifier(clarifier_id: int) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM reading_cards WHERE id = ? AND card_type = 'clarifier'",
            (clarifier_id,),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_clarifier_readings(record: ReadingRecord) -> list[ClarifierReading]:
    spread = get_spread(record.spread_id)
    if not spread:
        return []

    spread_map = {
        c.position_index: (c.card_id, c.is_reversed) for c in record.spread_cards
    }
    readings: list[ClarifierReading] = []
    for clarifier in record.clarifiers:
        if clarifier.clarifies_position is None:
            continue
        original = spread_map.get(clarifier.clarifies_position)
        if not original:
            continue
        position = spread.get_position(clarifier.clarifies_position)
        built = build_clarifier_reading(
            clarifier_id=clarifier.id or 0,
            clarifies_position=clarifier.clarifies_position,
            position=position,
            original_card_id=original[0],
            original_reversed=original[1],
            clarifier_card_id=clarifier.card_id,
            clarifier_reversed=clarifier.is_reversed,
        )
        if built:
            readings.append(built)
    return readings


def update_notes(reading_id: int, notes: str) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE readings SET notes = ? WHERE id = ?", (notes, reading_id))
        conn.commit()
    finally:
        conn.close()


def update_first_impression(reading_id: int, first_impression: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE readings SET first_impression = ? WHERE id = ?",
            (first_impression, reading_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_final_summary(reading_id: int, final_summary: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE readings SET final_summary = ? WHERE id = ?",
            (final_summary, reading_id),
        )
        conn.commit()
    finally:
        conn.close()


def count_due_reviews() -> int:
    conn = get_connection()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM readings "
            "WHERE review_due_at IS NOT NULL AND review_due_at != '' "
            "AND review_due_at <= ?",
            (today,),
        ).fetchone()
        return int(row["cnt"]) if row else 0
    finally:
        conn.close()


def update_outcome(
    reading_id: int,
    category: str,
    outcome_status: str,
    outcome_notes: str,
    review_due_at: str | None = None,
) -> None:
    conn = get_connection()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE readings SET category = ?, outcome_status = ?, "
            "outcome_notes = ?, reviewed_at = ?, review_due_at = ? WHERE id = ?",
            (category, outcome_status, outcome_notes, now, review_due_at, reading_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_ai_summary(reading_id: int, ai_summary: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE readings SET ai_summary = ? WHERE id = ?", (ai_summary, reading_id)
        )
        conn.commit()
    finally:
        conn.close()


def delete_reading(reading_id: int) -> bool:
    return delete_readings([reading_id]) > 0


def delete_readings(reading_ids: list[int]) -> int:
    ids = [i for i in reading_ids if isinstance(i, int) and i > 0]
    if not ids:
        return 0
    conn = get_connection()
    try:
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"DELETE FROM reading_cards WHERE reading_id IN ({placeholders})",
            ids,
        )
        cur = conn.execute(
            f"DELETE FROM readings WHERE id IN ({placeholders})",
            ids,
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
