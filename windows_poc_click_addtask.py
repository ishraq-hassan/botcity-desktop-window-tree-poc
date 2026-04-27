"""
BotCity Desktop POC #2: click every "Add task" button in Todoist and
dismiss the inline editor (Esc) afterwards. Time each click+dismiss cycle
and the full sweep.

Same attach pattern as poc_todoist.py — Todoist's window title is dynamic,
so we match by Electron class name + Todoist process exe.
"""

import sys
import time
from pathlib import Path

import psutil
from botcity.core import Backend, DesktopBot
from pywinauto import Desktop
from pywinauto.keyboard import send_keys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

APP_PATH = r"C:\Users\ishra\AppData\Local\Programs\todoist\Todoist.exe"


def find_todoist_window():
    todoist_pids = {
        p.info["pid"]
        for p in psutil.process_iter(["pid", "exe"])
        if p.info.get("exe") and Path(p.info["exe"]).resolve() == Path(APP_PATH).resolve()
    }
    deadline = time.perf_counter() + 30
    while time.perf_counter() < deadline:
        for w in Desktop(backend="uia").windows(class_name="Chrome_WidgetWin_1", visible_only=True):
            try:
                if w.process_id() in todoist_pids and w.rectangle().width() > 0:
                    return w
            except Exception:
                continue
        time.sleep(0.25)
    raise RuntimeError("No visible Todoist window found within 30s")


def main() -> None:
    bot = DesktopBot()

    t0 = time.perf_counter()
    try:
        bot.execute(APP_PATH)
    except Exception as exc:
        print(f"[warn] execute() raised {exc!r} — will try to attach anyway")
    bot.connect_to_app(Backend.UIA, path=APP_PATH, timeout=30)
    main_window = find_todoist_window()
    main_window.set_focus()
    t_attach = time.perf_counter() - t0
    print(f"Attach (launch+connect+find+focus): {t_attach:6.2f}s")
    print(f"Window: {main_window.window_text()!r}  rect={main_window.rectangle()}")

    t1 = time.perf_counter()
    buttons = main_window.descendants(control_type="Button")
    add_buttons = [b for b in buttons if (b.window_text() or "").strip() == "Add task"]
    t_find = time.perf_counter() - t1
    print(
        f"Find buttons (descendants scan):    {t_find:6.2f}s   ({len(buttons)} buttons total, {len(add_buttons)} 'Add task')"
    )

    if not add_buttons:
        print("No 'Add task' buttons found — aborting.")
        return

    per_button = []
    sweep_start = time.perf_counter()
    for i, btn in enumerate(add_buttons, 1):
        try:
            rect = btn.rectangle()
        except Exception:
            rect = None

        t_click_start = time.perf_counter()
        try:
            btn.click_input()
        except Exception as exc:
            print(f"  [{i}/{len(add_buttons)}] click failed: {exc!r}")
            continue
        t_clicked = time.perf_counter() - t_click_start

        # Brief pause so the inline editor materialises before we dismiss it.
        time.sleep(0.15)

        t_esc_start = time.perf_counter()
        send_keys("{ESC}")
        t_esc = time.perf_counter() - t_esc_start

        cycle = time.perf_counter() - t_click_start
        per_button.append(cycle)
        print(
            f"  [{i}/{len(add_buttons)}] rect={rect}  click={t_clicked * 1000:6.0f}ms  esc={t_esc * 1000:5.0f}ms  cycle={cycle * 1000:6.0f}ms"
        )

        time.sleep(0.05)

    t_sweep = time.perf_counter() - sweep_start

    print()
    print(f"Sweep total:   {t_sweep:6.2f}s   ({len(per_button)} buttons cycled)")
    if per_button:
        avg = sum(per_button) / len(per_button)
        print(
            f"Per-button avg: {avg * 1000:5.0f}ms   min={min(per_button) * 1000:5.0f}ms   max={max(per_button) * 1000:5.0f}ms"
        )
    print(f"GRAND TOTAL:   {time.perf_counter() - t0:6.2f}s")


if __name__ == "__main__":
    main()
