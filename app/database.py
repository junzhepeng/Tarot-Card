import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "tarot.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def _migrate_reading_cards(conn: sqlite3.Connection) -> None:
    if not _column_exists(conn, "reading_cards", "card_type"):
        conn.execute(
            "ALTER TABLE reading_cards ADD COLUMN card_type TEXT NOT NULL DEFAULT 'spread'"
        )
    if not _column_exists(conn, "reading_cards", "clarifies_position"):
        conn.execute("ALTER TABLE reading_cards ADD COLUMN clarifies_position INTEGER")


def _migrate_daily_cards(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL UNIQUE,
            card_id TEXT NOT NULL,
            is_reversed INTEGER NOT NULL DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )


def _migrate_custom_spreads(conn: sqlite3.Connection) -> None:
    if not _column_exists(conn, "custom_spreads", "category"):
        conn.execute(
            "ALTER TABLE custom_spreads ADD COLUMN category TEXT NOT NULL DEFAULT 'general'"
        )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS custom_spreads (
            id TEXT PRIMARY KEY,
            name_zh TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT NOT NULL DEFAULT 'general',
            card_count INTEGER NOT NULL,
            positions_json TEXT NOT NULL,
            layout_json TEXT NOT NULL,
            tips TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )


def _migrate_readings(conn: sqlite3.Connection) -> None:
    if not _column_exists(conn, "readings", "category"):
        conn.execute("ALTER TABLE readings ADD COLUMN category TEXT NOT NULL DEFAULT ''")
    if not _column_exists(conn, "readings", "outcome_status"):
        conn.execute(
            "ALTER TABLE readings ADD COLUMN outcome_status TEXT NOT NULL DEFAULT 'pending'"
        )
    if not _column_exists(conn, "readings", "outcome_notes"):
        conn.execute("ALTER TABLE readings ADD COLUMN outcome_notes TEXT NOT NULL DEFAULT ''")
    if not _column_exists(conn, "readings", "reviewed_at"):
        conn.execute("ALTER TABLE readings ADD COLUMN reviewed_at TEXT")
    if not _column_exists(conn, "readings", "querent"):
        conn.execute("ALTER TABLE readings ADD COLUMN querent TEXT NOT NULL DEFAULT ''")
    if not _column_exists(conn, "readings", "tags"):
        conn.execute("ALTER TABLE readings ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
    if not _column_exists(conn, "readings", "parent_reading_id"):
        conn.execute("ALTER TABLE readings ADD COLUMN parent_reading_id INTEGER")
    if not _column_exists(conn, "readings", "follow_up_note"):
        conn.execute(
            "ALTER TABLE readings ADD COLUMN follow_up_note TEXT NOT NULL DEFAULT ''"
        )
    if not _column_exists(conn, "readings", "first_impression"):
        conn.execute(
            "ALTER TABLE readings ADD COLUMN first_impression TEXT NOT NULL DEFAULT ''"
        )
    if not _column_exists(conn, "readings", "final_summary"):
        conn.execute(
            "ALTER TABLE readings ADD COLUMN final_summary TEXT NOT NULL DEFAULT ''"
        )
    if not _column_exists(conn, "readings", "review_due_at"):
        conn.execute("ALTER TABLE readings ADD COLUMN review_due_at TEXT")
    if not _column_exists(conn, "readings", "daily_entry_id"):
        conn.execute("ALTER TABLE readings ADD COLUMN daily_entry_id INTEGER")


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                spread_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                notes TEXT DEFAULT '',
                ai_summary TEXT,
                category TEXT NOT NULL DEFAULT '',
                outcome_status TEXT NOT NULL DEFAULT 'pending',
                outcome_notes TEXT NOT NULL DEFAULT '',
                reviewed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS reading_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reading_id INTEGER NOT NULL,
                position_index INTEGER NOT NULL,
                card_id TEXT NOT NULL,
                is_reversed INTEGER NOT NULL DEFAULT 0,
                card_type TEXT NOT NULL DEFAULT 'spread',
                clarifies_position INTEGER,
                FOREIGN KEY (reading_id) REFERENCES readings(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        _migrate_reading_cards(conn)
        _migrate_readings(conn)
        _migrate_custom_spreads(conn)
        _migrate_daily_cards(conn)
        conn.commit()
    finally:
        conn.close()


def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()
