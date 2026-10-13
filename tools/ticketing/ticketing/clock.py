"""Server clock synchronisation from the HTTP ``Date`` header.

``Date`` only has 1-second resolution, so a single sample is useless for an
open-at-exactly-HH:MM:00 race. Each sample instead *bounds* the offset:

    request sent at local t0, response at t1, header says second D
    => some t in [t0, t1] satisfies D <= t + offset < D + 1
    => offset in (D - t1, D + 1 - t0)

Intersecting those intervals, with each new request aimed at the predicted
second boundary, narrows the window to about half the RTT.
"""
from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Awaitable, Callable

import httpx

# (t0_local, t1_local, server_second) — all epoch seconds
Sample = tuple[float, float, int]
Fetcher = Callable[[], Awaitable[Sample]]


@dataclass(frozen=True)
class Offset:
    lo: float
    hi: float

    @property
    def value(self) -> float:
        """Best estimate of ``server_time - local_time`` in seconds."""
        return (self.lo + self.hi) / 2

    @property
    def error(self) -> float:
        """Half-width of the uncertainty window in seconds."""
        return (self.hi - self.lo) / 2


def intersect(samples: list[Sample]) -> Offset:
    if not samples:
        raise ValueError("no samples")
    lo = max(d - t1 for t0, t1, d in samples)
    hi = min(d + 1 - t0 for t0, t1, d in samples)
    if lo > hi:
        # Server clock stepped or a proxy cached Date; fall back to the
        # lowest-RTT sample instead of returning an inverted window.
        t0, t1, d = min(samples, key=lambda s: s[1] - s[0])
        mid = d + 0.5 - (t0 + t1) / 2
        half = (t1 - t0) / 2 + 0.5
        return Offset(mid - half, mid + half)
    return Offset(lo, hi)


def http_fetcher(client: httpx.AsyncClient, url: str) -> Fetcher:
    async def fetch() -> Sample:
        t0 = time.time()
        resp = await client.head(url, headers={"Cache-Control": "no-cache"})
        t1 = time.time()
        date = resp.headers.get("date")
        if not date:
            raise RuntimeError(f"{url} returned no Date header")
        return t0, t1, int(parsedate_to_datetime(date).timestamp())

    return fetch


async def measure(
    fetch: Fetcher,
    samples: int = 10,
    now: Callable[[], float] = time.time,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> Offset:
    """Binary-search the server's second boundary.

    After the first sample, each request is timed so its mid-flight moment
    lands on the *predicted* boundary; whichever second the server reports
    cuts the window on one side. ~1 s per sample, error ends near RTT jitter.
    """
    collected = [await fetch()]
    for _ in range(samples - 1):
        off = intersect(collected)
        half_rtt = min(t1 - t0 for t0, t1, _ in collected) / 2
        boundary = math.floor(now() + off.value + half_rtt + 0.05) + 1
        await sleep(max(0.0, boundary - off.value - half_rtt - now()))
        collected.append(await fetch())
    return intersect(collected)


async def sleep_until(target_epoch: float, offset: float, now: Callable[[], float] = time.time) -> None:
    """Sleep until server time reaches ``target_epoch``.

    Coarse ``asyncio.sleep`` until the last 50 ms, then short sleeps so the
    event loop stays responsive while hitting the mark within a few ms.
    """
    while True:
        remaining = target_epoch - (now() + offset)
        if remaining <= 0:
            return
        await asyncio.sleep(remaining - 0.05 if remaining > 0.1 else 0.001)
