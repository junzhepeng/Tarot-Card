from __future__ import annotations

from datetime import date, datetime

from app.database import get_connection
from app.models.daily import DailyEntry


def _row_to_entry(row) -> DailyEntry:
    return DailyEntry(
        id=row["id"],
        entry_date=row["entry_date"],
        card_id=row["card_id"],
        is_reversed=bool(row["is_reversed"]),
        notes=row["notes"] or "",
        created_at=row["created_at"],
    )


def get_entry_by_date(entry_date: str) -> DailyEntry | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM daily_cards WHERE entry_date = ?", (entry_date,)
        ).fetchone()
        return _row_to_entry(row) if row else None
    finally:
        conn.close()


def get_today_entry() -> DailyEntry | None:
    return get_entry_by_date(date.today().isoformat())


def save_daily_entry(
    card_id: str,
    is_reversed: bool = False,
    notes: str = "",
    entry_date: str | None = None,
) -> int:
    entry_date = entry_date or date.today().isoformat()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM daily_cards WHERE entry_date = ?", (entry_date,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE daily_cards SET card_id = ?, is_reversed = ?, notes = ?, created_at = ? "
                "WHERE entry_date = ?",
                (card_id, int(is_reversed), notes, now, entry_date),
            )
            conn.commit()
            return existing["id"]
        cur = conn.execute(
            "INSERT INTO daily_cards (entry_date, card_id, is_reversed, notes, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (entry_date, card_id, int(is_reversed), notes, now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_daily_entries(limit: int = 60) -> list[DailyEntry]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM daily_cards ORDER BY entry_date DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_entry(r) for r in rows]
    finally:
        conn.close()


def delete_daily_entry(entry_id: int) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM daily_cards WHERE id = ?", (entry_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def export_daily_raw() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM daily_cards ORDER BY entry_date").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def import_daily_raw(items: list[dict]) -> int:
    conn = get_connection()
    count = 0
    try:
        for item in items:
            conn.execute(
                "INSERT OR REPLACE INTO daily_cards "
                "(id, entry_date, card_id, is_reversed, notes, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    item["id"],
                    item["entry_date"],
                    item["card_id"],
                    int(item["is_reversed"]),
                    item.get("notes", ""),
                    item.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                ),
            )
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()
