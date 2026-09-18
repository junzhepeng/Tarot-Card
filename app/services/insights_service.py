from __future__ import annotations

from dataclasses import dataclass

from app.constants import OUTCOME_STATUSES
from app.database import get_connection


@dataclass
class CardFrequency:
    card_id: str
    draw_count: int
    reversed_count: int
    reading_count: int


def get_card_frequencies(querent: str = "", limit: int = 20) -> list[CardFrequency]:
    conn = get_connection()
    try:
        sql = (
            "SELECT rc.card_id, COUNT(*) AS draw_count, "
            "SUM(rc.is_reversed) AS reversed_count, "
            "COUNT(DISTINCT rc.reading_id) AS reading_count "
            "FROM reading_cards rc "
            "JOIN readings r ON r.id = rc.reading_id "
            "WHERE rc.card_type = 'spread'"
        )
        params: list = []
        if querent.strip():
            sql += " AND r.querent = ?"
            params.append(querent.strip())
        sql += (
            " GROUP BY rc.card_id ORDER BY draw_count DESC, rc.card_id LIMIT ?"
        )
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [
            CardFrequency(
                card_id=row["card_id"],
                draw_count=int(row["draw_count"]),
                reversed_count=int(row["reversed_count"] or 0),
                reading_count=int(row["reading_count"]),
            )
            for row in rows
        ]
    finally:
        conn.close()


def get_insights_overview(querent: str = "") -> dict:
    conn = get_connection()
    try:
        reading_where = ""
        card_join = (
            "FROM reading_cards rc JOIN readings r ON r.id = rc.reading_id "
            "WHERE rc.card_type = 'spread'"
        )
        params: list = []
        if querent.strip():
            reading_where = " WHERE querent = ?"
            card_join += " AND r.querent = ?"
            params = [querent.strip()]

        reading_count = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM readings{reading_where}",
            params[:1] if params else [],
        ).fetchone()["cnt"]

        card_row = conn.execute(
            f"SELECT COUNT(*) AS draws, COUNT(DISTINCT rc.card_id) AS unique_cards "
            f"{card_join}",
            params,
        ).fetchone()
        draw_count = int(card_row["draws"] or 0)
        unique_cards = int(card_row["unique_cards"] or 0)

        outcome_rows = conn.execute(
            f"SELECT outcome_status, COUNT(*) AS cnt FROM readings{reading_where} "
            "GROUP BY outcome_status",
            params[:1] if params else [],
        ).fetchall()
        outcome_stats = {
            row["outcome_status"]: int(row["cnt"]) for row in outcome_rows
        }
        outcome_labels = {
            key: {"label": OUTCOME_STATUSES.get(key, key), "count": count}
            for key, count in outcome_stats.items()
        }

        repeat_row = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM ("
            f"SELECT rc.card_id {card_join} GROUP BY rc.card_id HAVING COUNT(*) > 1"
            f")",
            params,
        ).fetchone()
        repeat_card_count = int(repeat_row["cnt"] or 0)

        return {
            "reading_count": int(reading_count),
            "draw_count": draw_count,
            "unique_cards": unique_cards,
            "repeat_card_count": repeat_card_count,
            "outcome_stats": outcome_labels,
        }
    finally:
        conn.close()
