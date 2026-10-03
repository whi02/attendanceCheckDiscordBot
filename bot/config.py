"""Settings loaded from environment variables (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    token: str
    attendance_channel_id: int
    study_role_id: int | None
    db_path: str


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Environment variable {name} is required (see .env.example)")
    return value


def _int(name: str, value: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise SystemExit(f"Environment variable {name} must be a numeric ID, got {value!r}")


def load_config() -> Config:
    load_dotenv()
    role = os.getenv("STUDY_ROLE_ID", "").strip()
    return Config(
        token=_required("DISCORD_TOKEN"),
        attendance_channel_id=_int("ATTENDANCE_CHANNEL_ID", _required("ATTENDANCE_CHANNEL_ID")),
        study_role_id=_int("STUDY_ROLE_ID", role) if role else None,
        db_path=os.getenv("DB_PATH", "").strip() or "attendance.db",
    )
