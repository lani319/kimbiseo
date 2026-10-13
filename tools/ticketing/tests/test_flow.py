"""End-to-end flow against local HTML fixtures in headless Chromium."""
from datetime import datetime, timedelta, timezone

import pytest

from ticketing import flow
from ticketing.config import parse

pw_api = pytest.importorskip("playwright.async_api")

EVENT = """
<button id="book" disabled>Book</button>
<script>
  setTimeout(() => document.getElementById('book').disabled = false, 300);
  document.getElementById('book').onclick = () => document.title = 'clicked';
</script>
"""

BOOKING = """
<ul id="dates"></ul><ul id="times"></ul><div id="log"></div>
<script>
  const log = m => document.getElementById('log').textContent += m + ';';
  setTimeout(() => {  // dates render late, top choice sold out
    document.getElementById('dates').innerHTML =
      '<li><button disabled>01/11</button></li><li><button>02/11</button></li>';
    document.querySelectorAll('#dates button').forEach(b => b.onclick = () => {
      log('date=' + b.textContent);
      document.getElementById('times').innerHTML =
        '<li><button>14:00</button></li><li><button>19:00</button></li>';
      document.querySelectorAll('#times button').forEach(t => t.onclick = () => {
        log('time=' + t.textContent);
        document.body.insertAdjacentHTML('beforeend', '<div id="captcha">captcha</div>');
      });
    });
  }, 200);
</script>
"""


def cfg(**over):
    raw = {
        "event_url": "about:blank",
        "open_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
        "selectors": {
            "book_button": "#book",
            "date_option": "#dates button:text-is('{value}')",
            "time_option": "#times button:text-is('{value}')",
            "handoff": "#captcha",
        },
        "preferences": {"dates": ["01/11", "02/11"], "times": ["19:00", "14:00"]},
        "open_timeout": 5,
        "step_timeout": 3,
    }
    raw.update(over)
    return parse(raw)


@pytest.fixture
async def page():
    async with pw_api.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception:
            browser = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = await browser.new_context()
        yield await ctx.new_page()
        await browser.close()


async def test_full_flow_falls_through_sold_out_date(page):
    await page.set_content(EVENT)
    c = cfg()
    btn = await flow.wait_for_open(page, c, offset=0.0)
    page2 = await flow.click_book(page, btn, popup_wait=0.2)
    assert page2 is page and await page.title() == "clicked"
    await page2.set_content(BOOKING)  # stands in for the post-click navigation
    assert await flow.pick(page2, c.selectors.date_option, c.dates, 3, "date") == "02/11"
    assert await flow.pick(page2, c.selectors.time_option, c.times, 3, "round") == "19:00"
    await flow.handoff(page2, c)
    assert await page2.locator("#log").text_content() == "date=02/11;time=19:00;"


async def test_click_book_follows_popup(page):
    await page.set_content('<button id="book" onclick="window.open(\'about:blank\')">Book</button>')
    target = await flow.click_book(page, page.locator("#book"))
    assert target is not page


async def test_waiting_room_blocks_until_cleared(page):
    await page.set_content(
        """<div id="queue">wait</div><button id="book">Book</button>
        <script>setTimeout(() => document.getElementById('queue').remove(), 1500)</script>"""
    )
    c = cfg(selectors={**cfg().selectors.__dict__, "waiting_room": "#queue"})
    btn = await flow.wait_for_open(page, c, offset=0.0)
    assert not await page.locator("#queue").count()
    assert await btn.is_enabled()


async def test_no_available_option_times_out(page):
    await page.set_content("<ul id='dates'><li><button disabled>01/11</button></li></ul>")
    with pytest.raises(flow.StepTimeout, match="date"):
        await flow.pick(page, "#dates button:text-is('{value}')", ["01/11"], 0.3, "date")


async def test_open_timeout(page):
    await page.set_content("<button id='book' disabled>Book</button>")
    c = cfg(open_timeout=0.3, reload_interval=0.5)
    with pytest.raises(flow.StepTimeout, match="book button"):
        await flow.wait_for_open(page, c, offset=0.0)
