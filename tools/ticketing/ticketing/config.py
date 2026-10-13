"""YAML config: what to book, when, and the site-specific selectors.

Selectors are kept out of code on purpose — the target site's DOM is unknown
until it is recorded with ``playwright codegen``, and it changes per event.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# Floor on reload frequency. Hammering the site gets the IP/account blocked
# by its WAF and degrades the sale for everyone else.
MIN_RELOAD_INTERVAL = 0.5


class ConfigError(ValueError):
    pass


@dataclass
class Selectors:
    book_button: str
    # Templates: "{value}" is replaced with each preference in order.
    date_option: str
    time_option: str
    # Optional: element that only exists once the date/time step is done
    # (e.g. the captcha box or seat map). The bot stops when it appears.
    handoff: str | None = None
    # Optional: element shown while the site's waiting room is active.
    # The bot just waits; it never tries to skip the queue.
    waiting_room: str | None = None


@dataclass
class Config:
    event_url: str
    open_at: datetime
    selectors: Selectors
    dates: list[str]
    times: list[str]
    login_url: str | None = None
    time_source_url: str | None = None
    lead_seconds: float = 0.0
    reload_interval: float = 1.0
    open_timeout: float = 600.0
    step_timeout: float = 15.0
    cdp_url: str | None = None
    user_data_dir: str = ".browser-profile"
    extra: dict[str, Any] = field(default_factory=dict)


def _require(d: dict[str, Any], key: str, where: str) -> Any:
    if key not in d or d[key] in (None, ""):
        raise ConfigError(f"{where}.{key} is required")
    return d[key]


def _str_list(value: Any, where: str) -> list[str]:
    if isinstance(value, (str, int)):
        value = [value]
    if not isinstance(value, list) or not value:
        raise ConfigError(f"{where} must be a non-empty list")
    return [str(v) for v in value]


def parse(raw: dict[str, Any]) -> Config:
    if not isinstance(raw, dict):
        raise ConfigError("config root must be a mapping")

    open_at = _require(raw, "open_at", "root")
    if isinstance(open_at, str):
        try:
            open_at = datetime.fromisoformat(open_at)
        except ValueError as e:
            raise ConfigError(f"open_at: {e}") from e
    if not isinstance(open_at, datetime) or open_at.tzinfo is None:
        # A naive time silently uses the PC's zone; the site is in Bangkok.
        raise ConfigError("open_at must include a UTC offset, e.g. 2026-11-01T10:00:00+07:00")

    sel = _require(raw, "selectors", "root")
    for key in ("date_option", "time_option"):
        if "{value}" not in str(_require(sel, key, "selectors")):
            raise ConfigError(f"selectors.{key} must contain '{{value}}'")
    selectors = Selectors(
        book_button=_require(sel, "book_button", "selectors"),
        date_option=sel["date_option"],
        time_option=sel["time_option"],
        handoff=sel.get("handoff"),
        waiting_room=sel.get("waiting_room"),
    )

    pref = _require(raw, "preferences", "root")
    reload_interval = float(raw.get("reload_interval", 1.0))
    if reload_interval < MIN_RELOAD_INTERVAL:
        raise ConfigError(f"reload_interval must be >= {MIN_RELOAD_INTERVAL}s")

    known = {
        "event_url", "open_at", "selectors", "preferences", "login_url", "time_source_url",
        "lead_seconds", "reload_interval", "open_timeout", "step_timeout", "cdp_url", "user_data_dir",
    }
    return Config(
        event_url=_require(raw, "event_url", "root"),
        open_at=open_at,
        selectors=selectors,
        dates=_str_list(_require(pref, "dates", "preferences"), "preferences.dates"),
        times=_str_list(_require(pref, "times", "preferences"), "preferences.times"),
        login_url=raw.get("login_url"),
        time_source_url=raw.get("time_source_url"),
        lead_seconds=float(raw.get("lead_seconds", 0.0)),
        reload_interval=reload_interval,
        open_timeout=float(raw.get("open_timeout", 600.0)),
        step_timeout=float(raw.get("step_timeout", 15.0)),
        cdp_url=raw.get("cdp_url"),
        user_data_dir=str(raw.get("user_data_dir", ".browser-profile")),
        extra={k: v for k, v in raw.items() if k not in known},
    )


def load(path: str | Path) -> Config:
    with open(path, encoding="utf-8") as f:
        return parse(yaml.safe_load(f))
