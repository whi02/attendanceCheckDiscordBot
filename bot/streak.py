"""Weekend checks and streak calculation.

Pure functions with no Discord dependency, so they can be tested directly.
A "weekend day" is Friday, Saturday or Sunday. Check-in on Friday opens at 17:00 KST.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

FRIDAY, SATURDAY, SUNDAY = 4, 5, 6
FRIDAY_OPEN = time(17, 0)
WEEKDAY_NAMES = "월화수목금토일"


def to_kst(dt: datetime) -> datetime:
    return dt.astimezone(KST)


def is_weekend(d: date) -> bool:
    return d.weekday() in (FRIDAY, SATURDAY, SUNDAY)


def prev_weekend_day(d: date) -> date:
    """Weekend day right before d. Friday goes back to last week's Sunday."""
    if d.weekday() == FRIDAY:
        return d - timedelta(days=5)
    return d - timedelta(days=1)


def latest_weekend_day_on_or_before(d: date) -> date:
    """d itself if it is a weekend day, otherwise the last Sunday."""
    if is_weekend(d):
        return d
    return d - timedelta(days=d.weekday() + 1)


def is_check_in_open(dt: datetime) -> bool:
    """Whether check-in is allowed at dt (Fri 17:00 ~ Sun 23:59:59 KST)."""
    local = to_kst(dt)
    weekday = local.weekday()
    if weekday in (SATURDAY, SUNDAY):
        return True
    return weekday == FRIDAY and local.time() >= FRIDAY_OPEN


def next_open_at(dt: datetime) -> datetime:
    """Next time check-in opens (Friday 17:00 KST) at or after dt."""
    local = to_kst(dt)
    days_ahead = (FRIDAY - local.weekday()) % 7
    friday = local.date() + timedelta(days=days_ahead)
    opens = datetime.combine(friday, FRIDAY_OPEN, tzinfo=KST)
    if opens < local:
        opens += timedelta(days=7)
    return opens


def weekend_of(d: date) -> tuple[date, date, date]:
    """Fri, Sat, Sun of the weekend containing d, or the upcoming one on Mon~Thu."""
    friday = d + timedelta(days=FRIDAY - d.weekday())
    return friday, friday + timedelta(days=1), friday + timedelta(days=2)


def current_streak(dates: Iterable[date], today: date) -> int:
    dates = set(dates)
    if not dates:
        return 0
    last = max(dates)
    alive = last == latest_weekend_day_on_or_before(today) or (
        is_weekend(today) and last == prev_weekend_day(today)
    )
    if not alive:
        return 0
    count, d = 1, last
    while prev_weekend_day(d) in dates:
        count += 1
        d = prev_weekend_day(d)
    return count


def next_weekend_day(d: date) -> date:
    """Weekend day right after d. Sunday goes forward to next Friday."""
    if d.weekday() == SUNDAY:
        return d + timedelta(days=5)
    return d + timedelta(days=1)


def best_streak(dates: Iterable[date]) -> int:
    dates = set(dates)
    best = 0
    for start in dates:
        # Only count from the first day of each run.
        if prev_weekend_day(start) in dates:
            continue
        length, d = 1, start
        while next_weekend_day(d) in dates:
            length += 1
            d = next_weekend_day(d)
        best = max(best, length)
    return best


@dataclass(frozen=True)
class StreakStats:
    current: int
    best: int
    total: int


def stats(dates: Iterable[date], today: date) -> StreakStats:
    dates = set(dates)
    return StreakStats(current_streak(dates, today), best_streak(dates), len(dates))


@dataclass(frozen=True)
class RankEntry:
    user_id: int
    rank: int | None  # None when the current streak is 0
    stats: StreakStats


def build_ranking(records: Mapping[int, Iterable[date]], today: date) -> list[RankEntry]:
    """Sort by current streak, then total, then user ID. Ties share a rank (1, 2, 2, 4)."""
    rows = [(user_id, stats(dates, today)) for user_id, dates in records.items()]
    rows.sort(key=lambda r: (-r[1].current, -r[1].total, r[0]))

    entries: list[RankEntry] = []
    prev_current, rank = None, 0
    for position, (user_id, s) in enumerate(rows, start=1):
        if s.current == 0:
            entries.append(RankEntry(user_id, None, s))
            continue
        if s.current != prev_current:
            rank, prev_current = position, s.current
        entries.append(RankEntry(user_id, rank, s))
    return entries


def format_day(d: date) -> str:
    """'10/3 토'"""
    return f"{d.month}/{d.day} {WEEKDAY_NAMES[d.weekday()]}"
