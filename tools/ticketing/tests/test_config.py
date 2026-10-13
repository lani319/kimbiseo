from pathlib import Path

import pytest
import yaml

from ticketing.config import ConfigError, load, parse

EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.yaml"


def base(**over):
    raw = {
        "event_url": "https://example.test/event",
        "open_at": "2026-11-01T10:00:00+07:00",
        "selectors": {
            "book_button": "#book",
            "date_option": "li:has-text('{value}')",
            "time_option": "li:has-text('{value}')",
        },
        "preferences": {"dates": ["01/11"], "times": ["19:00"]},
    }
    raw.update(over)
    return raw


def test_example_config_parses():
    cfg = load(EXAMPLE)
    assert cfg.open_at.utcoffset().total_seconds() == 7 * 3600
    assert cfg.dates and cfg.times


def test_minimal():
    cfg = parse(base())
    assert cfg.reload_interval == 1.0
    assert cfg.selectors.handoff is None


def test_scalar_preference_becomes_list():
    cfg = parse(base(preferences={"dates": "01/11", "times": 19}))
    assert cfg.dates == ["01/11"] and cfg.times == ["19"]


def test_yaml_native_datetime_accepted():
    raw = yaml.safe_load("open_at: 2026-11-01 10:00:00+07:00")
    cfg = parse(base(open_at=raw["open_at"]))
    assert cfg.open_at.hour == 10


@pytest.mark.parametrize(
    "over, msg",
    [
        ({"open_at": "2026-11-01T10:00:00"}, "UTC offset"),
        ({"open_at": "not a date"}, "open_at"),
        ({"reload_interval": 0.1}, "reload_interval"),
        ({"event_url": ""}, "event_url"),
        ({"preferences": {"dates": [], "times": ["1"]}}, "preferences.dates"),
        (
            {"selectors": {"book_button": "#b", "date_option": "li", "time_option": "li:{value}"}},
            "date_option",
        ),
    ],
)
def test_rejects(over, msg):
    with pytest.raises(ConfigError, match=msg):
        parse(base(**over))
