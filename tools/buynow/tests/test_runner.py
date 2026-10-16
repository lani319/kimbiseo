"""End-to-end against a local page whose button flips to 'BUY TICKET' at a given time."""

import os
import time
from datetime import datetime

import pytest

from buynow.runner import Config, Status, run
from buynow.schedule import KST

PAGE = """<!doctype html><html><body><div id="box"></div><script>
const openAt = Number(new URLSearchParams(location.search).get('open'));
const box = document.getElementById('box');
const b = document.createElement('button');
const isOpen = Date.now() >= openAt;
b.textContent = isOpen ? 'BUY TICKET' : 'COMING SOON';
b.disabled = !isOpen;
b.onclick = () => { document.title = 'clicked'; };
// SPA-style late render
setTimeout(() => box.appendChild(b), 100);
</script></body></html>"""


@pytest.fixture
def page_url(tmp_path):
    f = tmp_path / "shop.html"
    f.write_text(PAGE, encoding="utf-8")
    return f.as_uri()


def cfg(url, tmp_path, **kw):
    base = dict(
        url=url, xpath="//div[@id='box']/button", channel=None, headless=True,
        profile_dir=tmp_path / "profile", sync_clock=False, interval=0.5, jitter=0,
        find_timeout=1.0, keep_open=False,
        # CI uses `playwright install chromium`; sandboxes may point at a preinstalled one.
        executable_path=os.environ.get("BUYNOW_TEST_BROWSER") or None,
    )
    base.update(kw)
    return Config(**base)


async def test_waits_for_open_then_clicks(page_url, tmp_path):
    open_ts = time.time() + 3.0
    open_at = datetime.fromtimestamp(open_ts, KST)
    url = f"{page_url}?open={int(open_ts * 1000)}"
    t0 = time.time()
    result = await run(cfg(url, tmp_path, open_at=open_at, lead=1.5, give_up_after=10))
    assert result.status is Status.CLICKED
    assert time.time() >= open_ts  # never clicked before open
    assert time.time() - t0 < 8


async def test_gives_up_when_never_opens(page_url, tmp_path):
    open_ts = time.time() + 1.0
    url = f"{page_url}?open={int((open_ts + 3600) * 1000)}"  # button never flips
    result = await run(cfg(url, tmp_path, open_at=datetime.fromtimestamp(open_ts, KST),
                           lead=0.5, give_up_after=1.5))
    assert result.status is Status.GAVE_UP
    assert "COMING SOON" in result.text


async def test_dry_run_does_not_click_and_xpath_miss(page_url, tmp_path):
    url = f"{page_url}?open=0"
    r = await run(cfg(url, tmp_path, dry_run=True, max_attempts=1))
    assert r.status is Status.MATCHED
    r = await run(cfg(url, tmp_path, xpath="//a[@id='nope']", max_attempts=2))
    assert r.status is Status.NOT_FOUND
