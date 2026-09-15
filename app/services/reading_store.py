from __future__ import annotations

from datetime import datetime

from app.database import get_connection
from app.models.reading import DrawnCard, ReadingRecord


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
                "INSERT INTO reading_cards (reading_id, position_index, card_id, is_reversed) "
                "VALUES (?, ?, ?, ?)",
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
        card_rows = conn.execute(
            "SELECT position_index, card_id, is_reversed FROM reading_cards "
            "WHERE reading_id = ? ORDER BY position_index",
            (reading_id,),
        ).fetchall()
        cards = [
            DrawnCard(
                position_index=r["position_index"],
                card_id=r["card_id"],
                is_reversed=bool(r["is_reversed"]),
            )
            for r in card_rows
        ]
        return ReadingRecord(
            id=row["id"],
            question=row["question"],
            spread_id=row["spread_id"],
            created_at=row["created_at"],
            notes=row["notes"] or "",
            ai_summary=row["ai_summary"],
            cards=cards,
        )
    finally:
        conn.close()


def list_readings() -> list[ReadingRecord]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM readings ORDER BY created_at DESC").fetchall()
        results = []
        for row in rows:
            card_rows = conn.execute(
                "SELECT position_index, card_id, is_reversed FROM reading_cards "
                "WHERE reading_id = ? ORDER BY position_index",
                (row["id"],),
            ).fetchall()
            cards = [
                DrawnCard(
                    position_index=r["position_index"],
                    card_id=r["card_id"],
                    is_reversed=bool(r["is_reversed"]),
                )
                for r in card_rows
            ]
            results.append(
                ReadingRecord(
                    id=row["id"],
                    question=row["question"],
                    spread_id=row["spread_id"],
                    created_at=row["created_at"],
                    notes=row["notes"] or "",
                    ai_summary=row["ai_summary"],
                    cards=cards,
                )
            )
        return results
    finally:
        conn.close()


def update_notes(reading_id: int, notes: str) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE readings SET notes = ? WHERE id = ?", (notes, reading_id))
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
