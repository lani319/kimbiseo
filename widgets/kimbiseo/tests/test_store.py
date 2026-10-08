import json
from datetime import date

import pytest

from kimbiseo.store import Store, Task, format_dday, parse_due, sort_key

TODAY = date(2026, 10, 8)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("", None),
        ("  ", None),
        ("2026-10-15", date(2026, 10, 15)),
        ("2026.1.5", date(2026, 1, 5)),
        ("10-15", date(2026, 10, 15)),
        ("10/8", date(2026, 10, 8)),  # today is not rolled over
        ("1.5", date(2027, 1, 5)),  # already passed -> next year
        ("+3", date(2026, 10, 11)),
        ("오늘", TODAY),
        ("내일", date(2026, 10, 9)),
        ("모레", date(2026, 10, 10)),
    ],
)
def test_parse_due(text, expected):
    assert parse_due(text, today=TODAY) == expected


@pytest.mark.parametrize("text", ["abc", "13-01", "2026-02-30", "다음주"])
def test_parse_due_rejects_garbage(text):
    with pytest.raises(ValueError):
        parse_due(text, today=TODAY)


def test_format_dday():
    assert [format_dday(d) for d in (None, 0, 3, -2)] == ["-", "D-Day", "D-3", "D+2"]


def test_sort_open_by_deadline_then_undated_then_done():
    a = Task("late", due=date(2026, 10, 20))
    b = Task("soon", due=date(2026, 10, 9))
    c = Task("someday")
    d = Task("finished", due=date(2026, 10, 1), done=True)
    assert [t.title for t in sorted([d, c, a, b], key=sort_key)] == ["soon", "late", "someday", "finished"]


def test_round_trip_persists_tasks_and_settings(tmp_path):
    path = tmp_path / "tasks.json"
    s = Store(path)
    t = s.add("  보고서 작성 ", due=date(2026, 10, 15), assignee=" 김대리 ")
    s.set_setting("geometry", "300x400+1+2")

    reloaded = Store(path)
    assert reloaded.settings == {"geometry": "300x400+1+2"}
    [r] = reloaded.tasks
    assert (r.id, r.title, r.assignee, r.due, r.done) == (t.id, "보고서 작성", "김대리", date(2026, 10, 15), False)
    assert "보고서" in path.read_text(encoding="utf-8")  # stored as readable UTF-8


def test_update_toggle_remove_clear(tmp_path):
    s = Store(tmp_path / "tasks.json")
    a = s.add("A")
    b = s.add("B")
    s.update(a.id, title="A2", due=None, assignee="이과장")
    s.toggle(b.id)
    assert s.clear_done() == 1
    s.remove(a.id)
    assert Store(s.path).tasks == []


def test_blank_title_rejected(tmp_path):
    s = Store(tmp_path / "tasks.json")
    with pytest.raises(ValueError):
        s.add("   ")
    assert not s.path.exists()


def test_corrupt_file_is_preserved_not_overwritten(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text("{not json", encoding="utf-8")
    s = Store(path)
    assert s.tasks == []
    backups = list(tmp_path.glob("tasks.json.corrupt-*"))
    assert len(backups) == 1 and backups[0].read_text(encoding="utf-8") == "{not json"


def test_save_leaves_no_temp_files(tmp_path):
    s = Store(tmp_path / "tasks.json")
    s.add("A")
    assert [p.name for p in tmp_path.iterdir()] == ["tasks.json"]
    assert json.loads(s.path.read_text(encoding="utf-8"))["version"] == 1
