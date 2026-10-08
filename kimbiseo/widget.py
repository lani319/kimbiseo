"""Always-on-top desktop widget (tkinter, stdlib only)."""
from __future__ import annotations

import sys
import tkinter as tk
from datetime import date
from tkinter import font as tkfont

from .store import Store, Task, format_dday, parse_due

FONT_FAMILY = "Malgun Gothic" if sys.platform == "win32" else "TkDefaultFont"
RESIZE_CURSOR = "size_nw_se" if sys.platform == "win32" else "bottom_right_corner"

BG = "#1f2329"
BG_ROW = "#2a2f37"
BG_ROW_HOVER = "#343a44"
BG_INPUT = "#151a1f"
FG = "#e6e6e6"
FG_MUTED = "#8a919c"
ACCENT = "#5aa9e6"
ERROR = "#ff6b6b"

DEFAULT_GEOMETRY = "340x460+60+60"
MIN_W, MIN_H = 260, 200


def dday_color(days: int | None, done: bool) -> str:
    if done or days is None:
        return FG_MUTED
    if days < 0:
        return "#ff5c5c"  # overdue
    if days <= 1:
        return "#ff9f43"
    if days <= 3:
        return "#feca57"
    return "#7bd389"


class PlaceholderEntry(tk.Entry):
    """Entry that shows grey hint text while empty."""

    def __init__(self, master: tk.Misc, placeholder: str, **kw) -> None:
        super().__init__(master, **kw)
        self.placeholder = placeholder
        self._fg = kw.get("fg", FG)
        self._showing = False
        self.bind("<FocusIn>", self._clear_hint)
        self.bind("<FocusOut>", self._show_hint)
        self._show_hint()

    def _show_hint(self, _e=None) -> None:
        if not super().get():
            self._showing = True
            self.config(fg=FG_MUTED)
            self.insert(0, self.placeholder)

    def _clear_hint(self, _e=None) -> None:
        if self._showing:
            self.delete(0, tk.END)
            self.config(fg=self._fg)
            self._showing = False

    def get(self) -> str:  # type: ignore[override]
        return "" if self._showing else super().get()

    def set(self, value: str) -> None:
        self._clear_hint()
        self.delete(0, tk.END)
        self.insert(0, value)
        if self.focus_get() is not self:
            self._show_hint()


class KimbiseoWidget(tk.Tk):
    def __init__(self, store: Store | None = None) -> None:
        super().__init__()
        self.store = store or Store()
        self.editing_id: str | None = None
        self.collapsed = False
        self._rendered_on = date.today()
        self._drag_origin = (0, 0)

        self.font = tkfont.Font(family=FONT_FAMILY, size=10)
        self.font_done = tkfont.Font(family=FONT_FAMILY, size=10, overstrike=True)
        self.font_small = tkfont.Font(family=FONT_FAMILY, size=9)
        self.font_bold = tkfont.Font(family=FONT_FAMILY, size=10, weight="bold")

        self.title("김비서")
        self.configure(bg=BG)
        self.overrideredirect(True)  # frameless desktop widget
        self.geometry(self.store.settings.get("geometry", DEFAULT_GEOMETRY))
        self.attributes("-alpha", float(self.store.settings.get("alpha", 0.94)))
        self.topmost = bool(self.store.settings.get("topmost", True))
        self.attributes("-topmost", self.topmost)

        self._build_header()
        self._build_list()
        self._build_form()
        self.render()
        self.after(60_000, self._tick)

    # ---------- layout ----------
    def _build_header(self) -> None:
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill=tk.X, padx=8, pady=(6, 2))
        title = tk.Label(bar, text="김비서", bg=BG, fg=FG, font=self.font_bold)
        title.pack(side=tk.LEFT)
        self.count_label = tk.Label(bar, bg=BG, fg=FG_MUTED, font=self.font_small)
        self.count_label.pack(side=tk.LEFT, padx=6)

        self.btn_close = self._icon_button(bar, "✕", self.close)
        self.btn_collapse = self._icon_button(bar, "▾", self.toggle_collapse)
        self.btn_pin = self._icon_button(bar, "📌", self.toggle_topmost)
        self._refresh_pin()

        for w in (bar, title, self.count_label):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
            w.bind("<ButtonRelease-1>", lambda _e: self._save_geometry())

    def _icon_button(self, master: tk.Misc, text: str, command) -> tk.Label:
        b = tk.Label(master, text=text, bg=BG, fg=FG_MUTED, font=self.font, cursor="hand2", padx=4)
        b.pack(side=tk.RIGHT)
        b.bind("<Button-1>", lambda _e: command())
        b.bind("<Enter>", lambda _e: b.config(fg=FG))
        b.bind("<Leave>", lambda _e: self._refresh_pin() if b is self.btn_pin else b.config(fg=FG_MUTED))
        return b

    def _build_list(self) -> None:
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill=tk.BOTH, expand=True, padx=8)
        self.canvas = tk.Canvas(self.body, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.rows = tk.Frame(self.canvas, bg=BG)
        self._rows_win = self.canvas.create_window((0, 0), window=self.rows, anchor="nw")
        self.rows.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._rows_win, width=e.width))
        self.canvas.bind("<Enter>", lambda _e: self._bind_wheel(True))
        self.canvas.bind("<Leave>", lambda _e: self._bind_wheel(False))

    def _build_form(self) -> None:
        self.form = tk.Frame(self, bg=BG)
        self.form.pack(fill=tk.X, padx=8, pady=(4, 2))
        entry_kw = dict(bg=BG_INPUT, fg=FG, insertbackground=FG, relief=tk.FLAT, font=self.font)

        self.e_title = PlaceholderEntry(self.form, "업무명", **entry_kw)
        self.e_title.grid(row=0, column=0, columnspan=3, sticky="ew", ipady=3, pady=(0, 3))
        self.e_due = PlaceholderEntry(self.form, "기한 (10-15, +3, 내일)", width=14, **entry_kw)
        self.e_due.grid(row=1, column=0, sticky="ew", ipady=3)
        self.e_who = PlaceholderEntry(self.form, "담당자", width=8, **entry_kw)
        self.e_who.grid(row=1, column=1, sticky="ew", ipady=3, padx=3)
        self.btn_submit = tk.Button(
            self.form, text="추가", command=self.submit, bg=ACCENT, fg="#0b1a26",
            activebackground=ACCENT, relief=tk.FLAT, font=self.font_bold, padx=10, cursor="hand2",
        )
        self.btn_submit.grid(row=1, column=2, sticky="nsew")
        self.form.columnconfigure(0, weight=3)
        self.form.columnconfigure(1, weight=2)

        for e in (self.e_title, self.e_due, self.e_who):
            e.bind("<Return>", lambda _e: self.submit())
            e.bind("<Escape>", lambda _e: self.cancel_edit())

        self.footer = tk.Frame(self, bg=BG)
        self.footer.pack(fill=tk.X, padx=8, pady=(0, 4))
        self.msg = tk.Label(self.footer, bg=BG, fg=ERROR, font=self.font_small, anchor="w")
        self.msg.pack(side=tk.LEFT, fill=tk.X, expand=True)
        grip = tk.Label(self.footer, text="◢", bg=BG, fg=FG_MUTED, cursor=RESIZE_CURSOR)
        grip.pack(side=tk.RIGHT)
        grip.bind("<ButtonPress-1>", self._resize_start)
        grip.bind("<B1-Motion>", self._resize_move)
        grip.bind("<ButtonRelease-1>", lambda _e: self._save_geometry())
        clear = tk.Label(self.footer, text="완료 정리", bg=BG, fg=FG_MUTED, font=self.font_small, cursor="hand2")
        clear.pack(side=tk.RIGHT, padx=6)
        clear.bind("<Button-1>", lambda _e: self.clear_done())

    # ---------- rendering ----------
    def render(self) -> None:
        for child in self.rows.winfo_children():
            child.destroy()
        today = date.today()
        self._rendered_on = today
        tasks = self.store.sorted_tasks()
        for task in tasks:
            self._render_row(task, today)
        if not tasks:
            tk.Label(self.rows, text="등록된 업무가 없습니다.", bg=BG, fg=FG_MUTED, font=self.font_small).pack(pady=20)

        open_tasks = [t for t in tasks if not t.done]
        overdue = sum(1 for t in open_tasks if (t.days_left(today) or 0) < 0)
        text = f"진행 {len(open_tasks)}"
        if overdue:
            text += f" · 지연 {overdue}"
        self.count_label.config(text=text, fg="#ff5c5c" if overdue else FG_MUTED)

    def _render_row(self, task: Task, today: date) -> None:
        days = task.days_left(today)
        row = tk.Frame(self.rows, bg=BG_ROW, padx=6, pady=4)
        row.pack(fill=tk.X, pady=2)

        check = tk.Label(row, text="☑" if task.done else "☐", bg=BG_ROW, fg=ACCENT if task.done else FG_MUTED,
                         font=self.font, cursor="hand2")
        check.pack(side=tk.LEFT)
        check.bind("<Button-1>", lambda _e, i=task.id: self._toggle(i))

        dday = tk.Label(row, text=format_dday(days), bg=BG_ROW, fg=dday_color(days, task.done),
                        font=self.font_bold, width=6, anchor="e")
        dday.pack(side=tk.RIGHT)
        who = tk.Label(row, text=task.assignee, bg=BG_ROW, fg=FG_MUTED, font=self.font_small)
        who.pack(side=tk.RIGHT, padx=(4, 2))
        title = tk.Label(row, text=task.title, bg=BG_ROW, fg=FG_MUTED if task.done else FG,
                         font=self.font_done if task.done else self.font, anchor="w", justify=tk.LEFT)
        title.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        title.bind("<Configure>", lambda e, w=title: w.config(wraplength=max(e.width - 4, 40)))

        widgets = (row, dday, who, title)
        tip = task.due.isoformat() if task.due else ""
        for w in widgets:
            w.bind("<Enter>", lambda _e: self._hover(widgets, True, tip), add="+")
            w.bind("<Leave>", lambda _e: self._hover(widgets, False, ""), add="+")
            w.bind("<Double-Button-1>", lambda _e, t=task: self.start_edit(t))
            w.bind("<Button-3>", lambda e, t=task: self._context_menu(e, t))

    def _hover(self, widgets, on: bool, tip: str) -> None:
        for w in widgets:
            w.config(bg=BG_ROW_HOVER if on else BG_ROW)
        self.msg.config(text=f"기한 {tip}" if on and tip else "", fg=FG_MUTED)

    def _context_menu(self, event: tk.Event, task: Task) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="수정", command=lambda: self.start_edit(task))
        menu.add_command(label="완료 해제" if task.done else "완료", command=lambda: self._toggle(task.id))
        menu.add_separator()
        menu.add_command(label="삭제", command=lambda: self._remove(task.id))
        menu.tk_popup(event.x_root, event.y_root)

    # ---------- actions ----------
    def submit(self) -> None:
        try:
            due = parse_due(self.e_due.get())
            if self.editing_id:
                self.store.update(self.editing_id, title=self.e_title.get(), due=due, assignee=self.e_who.get())
            else:
                self.store.add(self.e_title.get(), due=due, assignee=self.e_who.get())
        except ValueError as exc:
            self.msg.config(text=str(exc), fg=ERROR)
            return
        except OSError as exc:
            self.msg.config(text=f"저장 실패: {exc}", fg=ERROR)
            return
        self.cancel_edit()
        self.e_title.focus_set()
        self.render()

    def start_edit(self, task: Task) -> None:
        self.editing_id = task.id
        self.e_title.set(task.title)
        self.e_due.set(task.due.isoformat() if task.due else "")
        self.e_who.set(task.assignee)
        self.btn_submit.config(text="수정")
        self.msg.config(text="수정 중 · Esc 취소", fg=FG_MUTED)
        self.e_title.focus_set()

    def cancel_edit(self) -> None:
        self.editing_id = None
        for e in (self.e_title, self.e_due, self.e_who):
            e.set("")
        self.btn_submit.config(text="추가")
        self.msg.config(text="")

    def _toggle(self, task_id: str) -> None:
        self.store.toggle(task_id)
        self.render()

    def _remove(self, task_id: str) -> None:
        if self.editing_id == task_id:
            self.cancel_edit()
        self.store.remove(task_id)
        self.render()

    def clear_done(self) -> None:
        removed = self.store.clear_done()
        self.render()
        self.msg.config(text=f"완료 {removed}건 정리" if removed else "정리할 완료 업무가 없습니다.", fg=FG_MUTED)

    def toggle_topmost(self) -> None:
        self.topmost = not self.topmost
        self.attributes("-topmost", self.topmost)
        self.store.set_setting("topmost", self.topmost)
        self._refresh_pin()

    def _refresh_pin(self) -> None:
        self.btn_pin.config(fg=ACCENT if self.topmost else FG_MUTED)

    def toggle_collapse(self) -> None:
        self.update_idletasks()  # make winfo_* reflect the real size
        self.collapsed = not self.collapsed
        if self.collapsed:
            self._expanded_height = self.winfo_height()
            self.body.pack_forget()
            self.form.pack_forget()
            self.footer.pack_forget()
            self.geometry(f"{self.winfo_width()}x34")
            self.btn_collapse.config(text="▸")
        else:
            self.body.pack(fill=tk.BOTH, expand=True, padx=8)
            self.form.pack(fill=tk.X, padx=8, pady=(4, 2))
            self.footer.pack(fill=tk.X, padx=8, pady=(0, 4))
            self.geometry(f"{self.winfo_width()}x{getattr(self, '_expanded_height', 460)}")
            self.btn_collapse.config(text="▾")

    def close(self) -> None:
        self._save_geometry()
        self.destroy()

    def _tick(self) -> None:
        # Re-render after midnight so D-day labels stay correct on a PC left running.
        if date.today() != self._rendered_on:
            self.render()
        self.after(60_000, self._tick)

    # ---------- window move / resize ----------
    def _drag_start(self, e: tk.Event) -> None:
        self._drag_origin = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())

    def _drag_move(self, e: tk.Event) -> None:
        dx, dy = self._drag_origin
        self.geometry(f"+{e.x_root - dx}+{e.y_root - dy}")

    def _resize_start(self, e: tk.Event) -> None:
        self._resize_origin = (e.x_root, e.y_root, self.winfo_width(), self.winfo_height())

    def _resize_move(self, e: tk.Event) -> None:
        x0, y0, w0, h0 = self._resize_origin
        w = max(MIN_W, w0 + e.x_root - x0)
        h = max(MIN_H, h0 + e.y_root - y0)
        self.geometry(f"{w}x{h}")

    def _save_geometry(self) -> None:
        if self.collapsed:
            geo = f"{self.winfo_width()}x{getattr(self, '_expanded_height', 460)}+{self.winfo_x()}+{self.winfo_y()}"
        else:
            geo = self.geometry()
        try:
            self.store.set_setting("geometry", geo)
        except OSError:
            pass  # position is a convenience; never block closing on it

    def _bind_wheel(self, on: bool) -> None:
        if on:
            self.bind_all("<MouseWheel>", self._on_wheel)  # Windows / macOS
            self.bind_all("<Button-4>", lambda _e: self.canvas.yview_scroll(-1, "units"))  # X11
            self.bind_all("<Button-5>", lambda _e: self.canvas.yview_scroll(1, "units"))
        else:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.unbind_all(seq)

    def _on_wheel(self, e: tk.Event) -> None:
        if self.rows.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-e.delta / 120) or (-1 if e.delta > 0 else 1), "units")


def main() -> None:
    KimbiseoWidget().mainloop()
