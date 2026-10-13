"""Booking steps against a Playwright page. Site-agnostic: all DOM knowledge
comes from ``config.Selectors``.

Steps: wait for open -> click Book (follow popup) -> pick date -> pick round
-> hand off to the human. Anything past the round (captcha, seats, payment)
is out of scope by design.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable

from playwright.async_api import Locator, Page

from .clock import sleep_until
from .config import Config

log = logging.getLogger(__name__)

POLL = 0.05  # in-page re-check interval (no network cost)


class StepTimeout(RuntimeError):
    pass


async def _ready(loc: Locator) -> bool:
    try:
        return await loc.is_visible() and await loc.is_enabled()
    except Exception:  # detached mid-check during a reload
        return False


async def wait_for_open(page: Page, cfg: Config, offset: float, now: Callable[[], float] = time.time) -> Locator:
    """Sleep until open time, then poll for an enabled Book button.

    Re-checks the live DOM every ``POLL`` (free) and reloads at most every
    ``reload_interval`` (costs a request). While the site's waiting room is
    showing it neither reloads nor clicks: reloading there loses your place.
    """
    target = cfg.open_at.timestamp() - cfg.lead_seconds
    log.info("waiting for open at %s (lead %.2fs)", cfg.open_at.isoformat(), cfg.lead_seconds)
    await sleep_until(target, offset, now)

    sel = cfg.selectors
    btn = page.locator(sel.book_button).first
    deadline = now() + cfg.open_timeout
    last_reload = now()
    while now() < deadline:
        if sel.waiting_room and await page.locator(sel.waiting_room).first.is_visible():
            log.info("in waiting room, holding")
            await asyncio.sleep(1.0)
            last_reload = now()
            continue
        if await _ready(btn):
            log.info("book button enabled")
            return btn
        if now() - last_reload >= cfg.reload_interval:
            last_reload = now()
            try:
                await page.reload(wait_until="domcontentloaded")
            except Exception as e:  # transient 5xx/timeouts are expected at open
                log.warning("reload failed: %s", e)
        await asyncio.sleep(POLL)
    raise StepTimeout(f"book button not enabled within {cfg.open_timeout:.0f}s")


async def click_book(page: Page, btn: Locator, popup_wait: float = 2.0) -> Page:
    """Click Book and return the page the flow continues on (popup or same tab)."""
    opened: list[Page] = []

    def on_page(p: Page) -> None:
        opened.append(p)

    page.context.on("page", on_page)
    try:
        await btn.click()
        end = time.monotonic() + popup_wait
        while not opened and time.monotonic() < end:
            await asyncio.sleep(POLL)
    finally:
        page.context.remove_listener("page", on_page)
    if opened:
        target = opened[-1]
        await target.wait_for_load_state("domcontentloaded")
        await target.bring_to_front()
        log.info("continuing in popup %s", target.url)
        return target
    return page


async def pick(page: Page, template: str, prefs: list[str], timeout: float, label: str) -> str:
    """Click the first preference that is visible and enabled.

    Loops over the whole list until ``timeout`` so a slow-rendering list or a
    sold-out top choice falls through to the next option instead of failing.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for value in prefs:
            loc = page.locator(template.replace("{value}", value)).first
            if await _ready(loc):
                await loc.click()
                log.info("%s selected: %s", label, value)
                return value
        await asyncio.sleep(POLL)
    raise StepTimeout(f"no {label} available from {prefs}")


async def handoff(page: Page, cfg: Config) -> None:
    if cfg.selectors.handoff:
        try:
            await page.locator(cfg.selectors.handoff).first.wait_for(timeout=cfg.step_timeout * 1000)
        except Exception:
            log.warning("handoff element not seen; handing off anyway")


async def book(page: Page, cfg: Config, offset: float, now: Callable[[], float] = time.time) -> Page:
    """Run the automated part. Returns the page the human should continue on."""
    btn = await wait_for_open(page, cfg, offset, now)
    page = await click_book(page, btn)
    await pick(page, cfg.selectors.date_option, cfg.dates, cfg.step_timeout, "date")
    await pick(page, cfg.selectors.time_option, cfg.times, cfg.step_timeout, "round")
    await handoff(page, cfg)
    return page
