from __future__ import annotations

from datetime import datetime

from app.database import get_connection
from app.models.reading import DrawnCard, ReadingRecord
from app.services.card_loader import get_spread
from app.services.clarifier import ClarifierReading, build_clarifier_reading


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
    )


def _load_cards_for_reading(conn, reading_id: int) -> list[DrawnCard]:
    card_rows = conn.execute(
        "SELECT id, position_index, card_id, is_reversed, card_type, clarifies_position "
        "FROM reading_cards WHERE reading_id = ? "
        "ORDER BY card_type, clarifies_position, id",
        (reading_id,),
    ).fetchall()
    return [_row_to_drawn_card(r) for r in card_rows]


def save_reading(
    question: str,
    spread_id: str,
    cards: list[tuple[int, str, bool]],
    notes: str = "",
    ai_summary: str | None = None,
) -> int:
    conn = get_connection()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute(
            "INSERT INTO readings (question, spread_id, created_at, notes, ai_summary) "
            "VALUES (?, ?, ?, ?, ?)",
            (question, spread_id, now, notes, ai_summary),
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

        sql += " ORDER BY created_at DESC"
        rows = conn.execute(sql, params).fetchall()

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


def update_outcome(
    reading_id: int,
    category: str,
    outcome_status: str,
    outcome_notes: str,
) -> None:
    conn = get_connection()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE readings SET category = ?, outcome_status = ?, "
            "outcome_notes = ?, reviewed_at = ? WHERE id = ?",
            (category, outcome_status, outcome_notes, now, reading_id),
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
