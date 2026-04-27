"""
POC #4: click every "Add task" button by iterating found_index.
No tree dump, no descendants() walk — just lazy lookups by index.
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
    except Exception:
        pass
    bot.connect_to_app(Backend.UIA, path=APP_PATH, timeout=30)
    main_window_wrapper = find_todoist_window()
    main_window_wrapper.set_focus()
    t_attach = time.perf_counter() - t0
    print(f"Attach: {t_attach * 1000:6.0f}ms")

    win_spec = Desktop(backend="uia").window(handle=main_window_wrapper.handle)

    sweep_start = time.perf_counter()
    cycles = []
    i = 0
    while True:
        cycle_start = time.perf_counter()

        try:
            btn = win_spec.child_window(title="Add task", control_type="Button", found_index=i)
            btn.wait("exists visible enabled", timeout=1)
        except Exception as exc:
            print(f"  index {i}: no more matches ({type(exc).__name__}) — stopping")
            break

        rect = btn.rectangle()
        t_locate = time.perf_counter() - cycle_start

        t_click_start = time.perf_counter()
        btn.click_input()
        t_click = time.perf_counter() - t_click_start

        time.sleep(0.15)

        t_esc_start = time.perf_counter()
        send_keys("{ESC}")
        t_esc = time.perf_counter() - t_esc_start

        cycle = time.perf_counter() - cycle_start
        cycles.append(cycle)
        print(
            f"  [{i}] rect={rect}  "
            f"locate={t_locate * 1000:5.0f}ms  click={t_click * 1000:5.0f}ms  "
            f"esc={t_esc * 1000:4.0f}ms  cycle={cycle * 1000:5.0f}ms"
        )

        time.sleep(0.05)
        i += 1

    sweep = time.perf_counter() - sweep_start
    print()
    print(f"Buttons clicked: {len(cycles)}")
    print(f"Sweep total:     {sweep * 1000:6.0f}ms")
    if cycles:
        avg = sum(cycles) / len(cycles)
        print(
            f"Per-button avg:  {avg * 1000:5.0f}ms   "
            f"min={min(cycles) * 1000:.0f}ms   max={max(cycles) * 1000:.0f}ms"
        )
    print(f"GRAND TOTAL:     {(time.perf_counter() - t0) * 1000:6.0f}ms")


if __name__ == "__main__":
    main()
