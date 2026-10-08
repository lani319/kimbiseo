"""Task model and JSON persistence for the Kimbiseo widget.

UI-agnostic on purpose: everything here is unit-testable without a display.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


@dataclass
class Task:
    title: str
    assignee: str = ""
    due: date | None = None
    done: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "assignee": self.assignee,
            "due": self.due.isoformat() if self.due else None,
            "done": self.done,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Task:
        due = d.get("due")
        return cls(
            id=str(d.get("id") or uuid.uuid4().hex),
            title=str(d.get("title", "")),
            assignee=str(d.get("assignee", "")),
            due=date.fromisoformat(due) if due else None,
            done=bool(d.get("done", False)),
        )

    def days_left(self, today: date | None = None) -> int | None:
        if self.due is None:
            return None
        return (self.due - (today or date.today())).days


_FULL_DATE = re.compile(r"^(\d{4})[-./](\d{1,2})[-./](\d{1,2})$")
_MONTH_DAY = re.compile(r"^(\d{1,2})[-./](\d{1,2})$")
_RELATIVE = re.compile(r"^\+(\d{1,3})$")
_KEYWORDS = {"오늘": 0, "today": 0, "내일": 1, "tomorrow": 1, "모레": 2}


def parse_due(text: str, today: date | None = None) -> date | None:
    """Parse a deadline typed by the user.

    Accepts: '' (no deadline), 2026-10-15, 2026.10.15, 10-15, 10/15,
    +3 (in 3 days), 오늘/내일/모레. A month-day that has already passed
    this year rolls over to next year. Raises ValueError otherwise.
    """
    s = text.strip().lower()
    if not s:
        return None
    today = today or date.today()

    if s in _KEYWORDS:
        return today + timedelta(days=_KEYWORDS[s])
    if m := _RELATIVE.match(s):
        return today + timedelta(days=int(m.group(1)))
    if m := _FULL_DATE.match(s):
        y, mo, d = map(int, m.groups())
        return date(y, mo, d)
    if m := _MONTH_DAY.match(s):
        mo, d = map(int, m.groups())
        candidate = date(today.year, mo, d)
        return candidate if candidate >= today else date(today.year + 1, mo, d)
    raise ValueError(f"기한 형식을 알 수 없습니다: {text!r}")


def format_dday(days: int | None) -> str:
    if days is None:
        return "-"
    if days == 0:
        return "D-Day"
    return f"D-{days}" if days > 0 else f"D+{-days}"


def sort_key(task: Task) -> tuple:
    # Open tasks first, then by nearest deadline; undated tasks sink below dated ones.
    return (task.done, task.due is None, task.due or date.max, task.title)


def default_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "kimbiseo" / "tasks.json"


class Store:
    """In-memory task list backed by an atomically written JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else default_path()
        self.tasks: list[Task] = []
        self.settings: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            tasks = [Task.from_dict(t) for t in raw.get("tasks", [])]
            settings = dict(raw.get("settings", {}))
        except (ValueError, TypeError, AttributeError):
            # Never overwrite a file we cannot read: keep it aside for manual recovery.
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            self.path.replace(self.path.with_name(f"{self.path.name}.corrupt-{stamp}"))
            return
        self.tasks, self.settings = tasks, settings

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": SCHEMA_VERSION,
            "tasks": [t.to_dict() for t in self.tasks],
            "settings": self.settings,
        }
        # Write to a temp file in the same dir, then rename: a crash mid-write
        # leaves the previous file intact instead of a truncated one.
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".tasks-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def sorted_tasks(self) -> list[Task]:
        return sorted(self.tasks, key=sort_key)

    def get(self, task_id: str) -> Task:
        return next(t for t in self.tasks if t.id == task_id)

    def add(self, title: str, due: date | None = None, assignee: str = "") -> Task:
        title = title.strip()
        if not title:
            raise ValueError("업무명을 입력하세요.")
        task = Task(title=title, due=due, assignee=assignee.strip())
        self.tasks.append(task)
        self.save()
        return task

    def update(self, task_id: str, *, title: str, due: date | None, assignee: str) -> None:
        title = title.strip()
        if not title:
            raise ValueError("업무명을 입력하세요.")
        task = self.get(task_id)
        task.title, task.due, task.assignee = title, due, assignee.strip()
        self.save()

    def toggle(self, task_id: str) -> None:
        task = self.get(task_id)
        task.done = not task.done
        self.save()

    def remove(self, task_id: str) -> None:
        self.tasks = [t for t in self.tasks if t.id != task_id]
        self.save()

    def clear_done(self) -> int:
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if not t.done]
        removed = before - len(self.tasks)
        if removed:
            self.save()
        return removed

    def set_setting(self, key: str, value: Any) -> None:
        self.settings[key] = value
        self.save()
