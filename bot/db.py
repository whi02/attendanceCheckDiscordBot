"""SQLite access. Streaks are never stored; they are computed from these rows."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance (
    guild_id   INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    date       TEXT    NOT NULL,
    checked_at TEXT    NOT NULL,
    source     TEXT    NOT NULL DEFAULT 'command',
    PRIMARY KEY (guild_id, user_id, date)
)
"""


class AttendanceDB:
    def __init__(self, path: str) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def add(
        self,
        guild_id: int,
        user_id: int,
        day: date,
        checked_at: datetime,
        source: str = "command",
    ) -> bool:
        """Insert a check-in. Returns False if that user already has one for that day."""
        with self.conn:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO attendance (guild_id, user_id, date, checked_at, source)"
                " VALUES (?, ?, ?, ?, ?)",
                (guild_id, user_id, day.isoformat(), checked_at.isoformat(), source),
            )
        return cur.rowcount == 1

    def remove(self, guild_id: int, user_id: int, day: date) -> bool:
        with self.conn:
            cur = self.conn.execute(
                "DELETE FROM attendance WHERE guild_id = ? AND user_id = ? AND date = ?",
                (guild_id, user_id, day.isoformat()),
            )
        return cur.rowcount == 1

    def user_dates(self, guild_id: int, user_id: int) -> set[date]:
        rows = self.conn.execute(
            "SELECT date FROM attendance WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return {date.fromisoformat(r[0]) for r in rows}

    def guild_dates(self, guild_id: int) -> dict[int, set[date]]:
        rows = self.conn.execute(
            "SELECT user_id, date FROM attendance WHERE guild_id = ?", (guild_id,)
        )
        result: dict[int, set[date]] = defaultdict(set)
        for user_id, day in rows:
            result[user_id].add(date.fromisoformat(day))
        return dict(result)
