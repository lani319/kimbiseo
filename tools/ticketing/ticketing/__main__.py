"""CLI.

    ticketing clock  config.yaml          # check server clock offset
    ticketing run    config.yaml          # real run at open_at
    ticketing run    config.yaml --now    # rehearsal: skip the wait
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator
from urllib.parse import urlsplit

import httpx
from playwright.async_api import BrowserContext, async_playwright

from . import clock, flow
from .config import Config, ConfigError, load
from .notify import alert

log = logging.getLogger("ticketing")


def _time_source(cfg: Config) -> str:
    if cfg.time_source_url:
        return cfg.time_source_url
    u = urlsplit(cfg.event_url)
    return f"{u.scheme}://{u.netloc}/"


async def measure_offset(cfg: Config) -> clock.Offset:
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True, http2=False) as client:
        off = await clock.measure(clock.http_fetcher(client, _time_source(cfg)))
    log.info("server offset %+.3fs (±%.3fs) via %s", off.value, off.error, _time_source(cfg))
    return off


@asynccontextmanager
async def open_context(cfg: Config) -> AsyncIterator[BrowserContext]:
    """Either attach to the user's own Chrome (cdp_url) or launch a visible,
    persistent profile so the login survives between runs."""
    async with async_playwright() as pw:
        if cfg.cdp_url:
            browser = await pw.chromium.connect_over_cdp(cfg.cdp_url)
            yield browser.contexts[0] if browser.contexts else await browser.new_context()
        else:
            ctx = await pw.chromium.launch_persistent_context(cfg.user_data_dir, headless=False, no_viewport=True)
            try:
                yield ctx
            finally:
                await ctx.close()


async def cmd_clock(cfg: Config) -> int:
    off = await measure_offset(cfg)
    server_now = datetime.fromtimestamp(time.time() + off.value, tz=cfg.open_at.tzinfo)
    print(f"offset   {off.value:+.3f}s  (±{off.error * 1000:.0f} ms)")
    print(f"server   {server_now.isoformat(timespec='milliseconds')}")
    print(f"open in  {cfg.open_at.timestamp() - server_now.timestamp():,.1f}s")
    return 0


async def cmd_run(cfg: Config, now_mode: bool) -> int:
    if now_mode:
        cfg.open_at = datetime.now(timezone.utc)
        cfg.lead_seconds = 0.0
        offset = 0.0
    else:
        offset = (await measure_offset(cfg)).value

    async with open_context(cfg) as ctx:
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        if cfg.login_url:
            await page.goto(cfg.login_url)
            # Login and any verification are done by the human, never automated.
            await asyncio.to_thread(input, "로그인을 직접 완료한 뒤 Enter를 누르세요... ")
        await page.goto(cfg.event_url, wait_until="domcontentloaded")

        try:
            page = await flow.book(page, cfg, offset)
        except flow.StepTimeout as e:
            alert(f"자동 단계 실패: {e} — 브라우저에서 직접 진행하세요")
        else:
            alert("날짜/회차 선택 완료 — 보안문자·좌석·결제를 직접 진행하세요")

        # Keep the browser alive for the human; Ctrl+C to exit.
        await asyncio.to_thread(input, "끝나면 Enter를 눌러 종료... ")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ticketing")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("clock", "run"):
        sp = sub.add_parser(name)
        sp.add_argument("config")
        if name == "run":
            sp.add_argument("--now", action="store_true", help="rehearsal: ignore open_at and start immediately")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s.%(msecs)03d %(message)s", datefmt="%H:%M:%S")
    try:
        cfg = load(args.config)
    except (OSError, ConfigError) as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    try:
        if args.cmd == "clock":
            return asyncio.run(cmd_clock(cfg))
        return asyncio.run(cmd_run(cfg, args.now))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
