from datetime import datetime, timedelta, timezone

import pytest

from buynow.cli import parse_args
from buynow.matcher import matches, normalize
from buynow.schedule import KST, Clock, offset_from_date_header, parse_kst


@pytest.mark.parametrize("raw", ["BUY TICKET", " buy\nticket ", "Buy Ticket", "ＢＵＹ ＴＩＣＫＥＴ"])
def test_normalize_equivalents(raw):
    assert normalize(raw) == "buy ticket"


def test_exact_vs_contains():
    assert matches("BUY TICKET", "BUY TICKET")
    assert not matches("BUY TICKET (R석)", "BUY TICKET")
    assert matches("BUY TICKET (R석)", "BUY TICKET", exact=False)
    assert not matches("SOLD OUT", "BUY TICKET", exact=False)
    assert not matches("anything", "")
    assert not matches(None, "BUY TICKET")


def test_parse_kst_naive_is_kst():
    dt = parse_kst("2026-10-20 20:00")
    assert dt.utcoffset() == timedelta(hours=9)
    assert dt.astimezone(timezone.utc) == datetime(2026, 10, 20, 11, 0, tzinfo=timezone.utc)


def test_parse_kst_explicit_offset_kept():
    assert parse_kst("2026-10-20T11:00:00Z") == datetime(2026, 10, 20, 20, 0, tzinfo=KST)


def test_offset_from_date_header():
    # server says 11:00:00 (true time in [00, 01)); local sent/received around 10:59:58
    server = datetime(2026, 10, 20, 11, 0, 0, tzinfo=timezone.utc).timestamp()
    sent, received = server - 2.2, server - 2.0
    off = offset_from_date_header("Tue, 20 Oct 2026 11:00:00 GMT", sent, received)
    assert off == pytest.approx(2.6)  # 0.5 centring + 2.1 behind


def test_clock_until():
    target = datetime(2026, 10, 20, 20, 0, tzinfo=KST)
    c = Clock(offset=1.0, now=lambda: target.timestamp() - 11.0)
    assert c.until(target) == pytest.approx(10.0)


def test_cli_defaults_and_guards():
    cfg = parse_args(["https://x", "//button", "--at", "2026-10-20 20:00"])
    assert cfg.expected == "BUY TICKET" and cfg.lead == 10.0 and cfg.channel == "msedge"
    assert cfg.open_at == datetime(2026, 10, 20, 20, 0, tzinfo=KST)
    with pytest.raises(SystemExit):
        parse_args(["https://x", "//b", "--interval", "0.1"])
    with pytest.raises(SystemExit):
        parse_args(["https://x", "//b", "--at", "tomorrow 8pm"])


def test_prompt_argv_builds_cli_args():
    from buynow.cli import prompt_argv

    answers = iter(["https://x", "//button", "2026-10-20 20:00:00", ""])
    argv = prompt_argv(ask=lambda _: next(answers))
    cfg = parse_args(argv)
    assert cfg.expected == "BUY TICKET"
    assert cfg.open_at == datetime(2026, 10, 20, 20, 0, tzinfo=KST)
