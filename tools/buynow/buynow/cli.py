from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from buynow.runner import MIN_INTERVAL, Config, Status, run
from buynow.schedule import parse_kst


def parse_args(argv: list[str] | None = None) -> Config:
    p = argparse.ArgumentParser(
        prog="buynow",
        description="At OPEN time (KST), reload URL until the element at XPATH reads TEXT, then click it.",
    )
    p.add_argument("url")
    p.add_argument("xpath", help='e.g. "//button[@id=\'buy\']"')
    p.add_argument("--at", help='open time in KST, e.g. "2026-10-20 20:00:00" (omit = start now)')
    p.add_argument("--lead", type=float, default=10.0, help="start reloading N sec before --at")
    p.add_argument("--give-up", type=float, default=300.0, help="stop N sec after --at (0 = never)")
    p.add_argument("--text", default="BUY TICKET", help="expected label (case/space-insensitive)")
    p.add_argument("--contains", action="store_true", help="match if label contains --text")
    p.add_argument("--interval", type=float, default=1.0, help="seconds between reloads")
    p.add_argument("--jitter", type=float, default=0.2, help="random extra delay 0..N sec")
    p.add_argument("--max-attempts", type=int, default=0, help="0 = unlimited")
    p.add_argument("--timeout", type=float, default=2.0, help="seconds to wait for XPath per load")
    p.add_argument("--no-sync-clock", action="store_true", help="trust local PC clock as-is")
    p.add_argument(
        "--browser", default="msedge", choices=["msedge", "chrome", "chromium"],
        help="msedge/chrome use the installed browser; chromium needs `playwright install`",
    )
    p.add_argument("--browser-path", type=Path, help="Chromium-based browser exe (e.g. Whale); overrides --browser")
    p.add_argument("--profile", type=Path, default=Path.home() / ".buynow" / "profile")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="verify only, never click")
    p.add_argument("--exit-after-click", action="store_true", help="close browser after click")
    a = p.parse_args(argv)

    if a.interval < MIN_INTERVAL:
        p.error(f"--interval must be >= {MIN_INTERVAL}s")
    try:
        open_at = parse_kst(a.at) if a.at else None
    except ValueError:
        p.error(f'--at: cannot parse {a.at!r}; use "YYYY-MM-DD HH:MM[:SS]"')
    return Config(
        url=a.url,
        xpath=a.xpath,
        expected=a.text,
        exact=not a.contains,
        open_at=open_at,
        lead=max(0.0, a.lead),
        give_up_after=max(0.0, a.give_up),
        interval=a.interval,
        jitter=max(0.0, a.jitter),
        max_attempts=max(0, a.max_attempts),
        find_timeout=a.timeout,
        sync_clock=not a.no_sync_clock,
        channel=None if a.browser == "chromium" else a.browser,
        executable_path=a.browser_path,
        profile_dir=a.profile,
        headless=a.headless,
        dry_run=a.dry_run,
        keep_open=not a.exit_after_click,
    )


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s.%(msecs)03d %(message)s", datefmt="%H:%M:%S")
    cfg = parse_args(argv)
    try:
        result = asyncio.run(run(cfg))
    except KeyboardInterrupt:
        logging.getLogger("buynow").info("stopped by user")
        return 130
    return 0 if result.status in (Status.CLICKED, Status.MATCHED) else 1
