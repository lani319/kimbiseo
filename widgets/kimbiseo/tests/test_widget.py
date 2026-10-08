"""GUI smoke test: builds the real widget and drives it through the form.

Skipped when no display is available (e.g. headless Linux without xvfb-run).
"""
from datetime import date, timedelta

import pytest

tk = pytest.importorskip("tkinter")

from kimbiseo.store import Store  # noqa: E402
from kimbiseo.widget import KimbiseoWidget  # noqa: E402


@pytest.fixture
def widget(tmp_path):
    try:
        w = KimbiseoWidget(Store(tmp_path / "tasks.json"))
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    w.update()
    yield w
    try:
        w.destroy()
    except tk.TclError:
        pass  # already destroyed by the test (e.g. close())


def fill(w, title, due, who):
    w.e_title.set(title)
    w.e_due.set(due)
    w.e_who.set(who)
    w.submit()


def test_add_edit_toggle_collapse(widget):
    w = widget
    fill(w, "주간 보고서", "+1", "김대리")
    fill(w, "지연 업무", (date.today() - timedelta(days=2)).isoformat(), "박차장")
    assert [t.title for t in w.store.sorted_tasks()] == ["지연 업무", "주간 보고서"]
    assert w.count_label.cget("text") == "진행 2 · 지연 1"

    target = w.store.sorted_tasks()[1]
    w.start_edit(target)
    w.e_who.set("최부장")
    w.submit()
    assert w.store.get(target.id).assignee == "최부장"
    assert w.btn_submit.cget("text") == "추가"

    w._toggle(target.id)
    assert w.store.get(target.id).done

    w.toggle_collapse()
    w.toggle_collapse()
    w.update()
    assert w.winfo_width() > 1 and w.winfo_height() > 34


def test_invalid_input_shows_error_without_saving(widget):
    w = widget
    fill(w, "", "", "")
    assert w.msg.cget("text") == "업무명을 입력하세요."
    fill(w, "x", "abc", "")
    assert "기한 형식" in w.msg.cget("text")
    assert w.store.tasks == []


def test_close_persists_geometry(widget, tmp_path):
    widget.close()
    assert "geometry" in Store(tmp_path / "tasks.json").settings
