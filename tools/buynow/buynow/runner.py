"""Wait for open time -> reload -> locate XPath -> verify label -> click."""

from __future__ import annotations

import asyncio
import enum
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from playwright.async_api import BrowserContext, Error as PlaywrightError, Page
from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from buynow.matcher import matches
from buynow.schedule import KST, Clock, offset_from_date_header

log = logging.getLogger("buynow")

MIN_INTERVAL = 0.5  # seconds; below this you are effectively DoS-ing the site


class Status(enum.Enum):
    NOT_FOUND = "not_found"
    TEXT_MISMATCH = "text_mismatch"
    NOT_CLICKABLE = "not_clickable"
    CLICKED = "clicked"
    MATCHED = "matched (dry-run, not clicked)"
    GAVE_UP = "gave_up"


@dataclass(frozen=True)
class Probe:
    status: Status
    text: str = ""


@dataclass(frozen=True)
class Config:
    url: str
    xpath: str
    expected: str = "BUY TICKET"
    exact: bool = True
    open_at: datetime | None = None  # None = start immediately
    lead: float = 10.0  # start reloading this many seconds before open_at
    give_up_after: float = 300.0  # stop this many seconds after open_at (0 = never)
    interval: float = 1.0
    jitter: float = 0.2
    max_attempts: int = 0  # 0 = unlimited
    find_timeout: float = 2.0
    sync_clock: bool = True  # align to the site's HTTP Date header
    channel: str | None = "msedge"  # Edge ships with Windows 11 -> no browser download
    executable_path: Path | None = None  # any Chromium-based exe (Whale, portable Chrome); overrides channel
    profile_dir: Path = field(default_factory=lambda: Path.home() / ".buynow" / "profile")
    headless: bool = False
    dry_run: bool = False
    keep_open: bool = True


async def read_label(page: Page, xpath: str, timeout_ms: float):
    """Return (locator, label) or None if the XPath matches nothing in time."""
    loc = page.locator(f"xpath={xpath}").first
    try:
        await loc.wait_for(state="attached", timeout=timeout_ms)
    except PlaywrightTimeout:
        return None
    # <input type=submit value="BUY TICKET"> has no innerText; fall back to value / aria-label.
    text = await loc.evaluate(
        "el => (el.innerText || el.value || el.getAttribute('aria-label') || el.textContent || '')"
    )
    return loc, text


async def probe_and_click(page: Page, cfg: Config) -> Probe:
    found = await read_label(page, cfg.xpath, cfg.find_timeout * 1000)
    if found is None:
        return Probe(Status.NOT_FOUND)
    loc, text = found
    if not matches(text, cfg.expected, exact=cfg.exact):
        return Probe(Status.TEXT_MISMATCH, text)
    if not (await loc.is_visible() and await loc.is_enabled()):
        return Probe(Status.NOT_CLICKABLE, text)
    if cfg.dry_run:
        return Probe(Status.MATCHED, text)
    # Scrolls into view, waits for stability, then dispatches real mouse
    # down/up at the element centre (trusted input, not el.click()).
    await loc.click(timeout=cfg.find_timeout * 1000)
    return Probe(Status.CLICKED, text)


async def watch(page: Page, cfg: Config, clock: Clock, *, reload_first: bool) -> Probe:
    """Reload/probe loop until clicked, max_attempts, or give-up deadline."""
    deadline = None
    if cfg.open_at is not None and cfg.give_up_after > 0:
        deadline = cfg.open_at.timestamp() + cfg.give_up_after

    attempt = 0
    last = Probe(Status.NOT_FOUND)
    while cfg.max_attempts == 0 or attempt < cfg.max_attempts:
        if deadline is not None and clock.now() >= deadline:
            log.warning("gave up %.0fs after open time", cfg.give_up_after)
            return Probe(Status.GAVE_UP, last.text)
        attempt += 1
        started = time.monotonic()
        try:
            if attempt > 1 or reload_first:
                await page.reload(wait_until="domcontentloaded")
            last = await probe_and_click(page, cfg)
        except PlaywrightError as e:  # 5xx/queue page, SPA re-render detaching the node, ...
            log.warning("#%d %s", attempt, str(e).splitlines()[0])
        else:
            log.info("#%d %s %r", attempt, last.status.value, last.text.strip()[:40])
            if last.status in (Status.CLICKED, Status.MATCHED):
                return last
        # Interval is reload-to-reload, so slow page loads don't add up.
        pause = cfg.interval + random.uniform(0, cfg.jitter) - (time.monotonic() - started)
        await asyncio.sleep(max(0.0, pause))
    return last


async def sync_clock(ctx: BrowserContext, url: str) -> Clock:
    """Estimate local->server offset from the HTTP Date header (median of 3)."""
    samples = []
    for _ in range(3):
        sent = time.time()
        try:
            resp = await ctx.request.head(url, timeout=5000)
        except PlaywrightError as e:
            log.warning("clock sync failed: %s", str(e).splitlines()[0])
            continue
        received = time.time()
        date = resp.headers.get("date")
        if date:
            samples.append(offset_from_date_header(date, sent, received))
    if not samples:
        log.warning("no Date header; using local clock (sync Windows time manually!)")
        return Clock()
    offset = sorted(samples)[len(samples) // 2]
    log.info("server clock offset %+.3fs (local %s server)", offset, "behind" if offset > 0 else "ahead of")
    return Clock(offset)


async def wait_until(clock: Clock, target: float) -> None:
    """Coarse sleeps with a countdown log, then a precise final sleep."""
    while (remaining := target - clock.now()) > 0:
        if remaining > 60:
            log.info("T-%dm%02ds", remaining // 60, remaining % 60)
            await asyncio.sleep(min(remaining - 30, 60))
        else:
            await asyncio.sleep(remaining)


async def _open(cfg: Config, pw) -> BrowserContext:
    # Persistent profile keeps login / cookies between runs: log in once, reuse.
    cfg.profile_dir.mkdir(parents=True, exist_ok=True)
    return await pw.chromium.launch_persistent_context(
        str(cfg.profile_dir),
        channel=None if cfg.executable_path else cfg.channel,
        executable_path=str(cfg.executable_path) if cfg.executable_path else None,
        headless=cfg.headless,
        no_viewport=True,
        args=["--start-maximized"],
    )


async def run(cfg: Config) -> Probe:
    async with async_playwright() as pw:
        ctx = await _open(cfg, pw)
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.goto(cfg.url, wait_until="domcontentloaded")

            clock = Clock()
            if cfg.open_at is not None:
                if cfg.sync_clock:
                    clock = await sync_clock(ctx, cfg.url)
                start = cfg.open_at.timestamp() - cfg.lead
                log.info(
                    "open %s, reloading from T-%.0fs (log in now if needed)",
                    cfg.open_at.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S KST"), cfg.lead,
                )
                await wait_until(clock, start)

            result = await watch(page, cfg, clock, reload_first=cfg.open_at is not None)
            if result.status is Status.CLICKED and cfg.keep_open and not cfg.headless:
                log.info("Clicked. Finish checkout in the browser; close it to exit.")
                await ctx.wait_for_event("close", timeout=0)
            return result
        finally:
            try:
                await ctx.close()
            except PlaywrightError:
                pass
