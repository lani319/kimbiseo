"""KST open-time parsing and wall-clock alignment (pure, Playwright-free)."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# Korea has no DST, so a fixed offset is exact and needs no tzdata on Windows.
KST = timezone(timedelta(hours=9), "KST")


def parse_kst(value: str) -> datetime:
    """'2026-10-20 20:00', '2026-10-20 20:00:00', '2026-10-20T20:00:00' -> aware KST datetime.
    An explicit offset in the string (e.g. '+09:00', 'Z') is honoured as-is."""
    dt = datetime.fromisoformat(value.strip().replace(" ", "T", 1))
    return dt.replace(tzinfo=KST) if dt.tzinfo is None else dt


def offset_from_date_header(date_header: str, sent_at: float, received_at: float) -> float:
    """Seconds to ADD to local time.time() to get server time.

    HTTP Date has 1s resolution and is truncated, so the true server time at
    receipt is in [Date, Date+1); +0.5 centres the estimate. RTT/2 accounts for
    the response travelling back. Expected error is about ±0.5s.
    """
    server = parsedate_to_datetime(date_header).timestamp() + 0.5
    midpoint = (sent_at + received_at) / 2
    return server - midpoint


class Clock:
    """Wall clock with an optional offset (local -> server)."""

    def __init__(self, offset: float = 0.0, now=time.time):
        self.offset = offset
        self._now = now

    def now(self) -> float:
        return self._now() + self.offset

    def until(self, target: datetime) -> float:
        return target.timestamp() - self.now()
