"""
POC #3: click ONE "Add task" button without enumerating the tree.
Uses pywinauto's lazy child_window() lookup — UIA short-circuits on first match.
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
        if p.info.get("exe")
        and Path(p.info["exe"]).resolve() == Path(APP_PATH).resolve()
    }
    deadline = time.perf_counter() + 30
    while time.perf_counter() < deadline:
        for w in Desktop(backend="uia").windows(
            class_name="Chrome_WidgetWin_1", visible_only=True
        ):
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
    print(f"Attach:        {t_attach * 1000:6.0f}ms")

    win_spec = Desktop(backend="uia").window(handle=main_window_wrapper.handle)

    # Lazy lookup — pywinauto walks UIA until it finds the first match,
    # then stops. No full tree dump.
    t1 = time.perf_counter()
    add_btn = win_spec.child_window(
        title="Add task", control_type="Button", found_index=0
    )
    add_btn.wait("exists visible enabled", timeout=10)
    t_locate = time.perf_counter() - t1
    print(f"Locate button: {t_locate * 1000:6.0f}ms   rect={add_btn.rectangle()}")

    t2 = time.perf_counter()
    add_btn.click_input()
    t_click = time.perf_counter() - t2
    print(f"Click:         {t_click * 1000:6.0f}ms")

    time.sleep(0.15)

    t3 = time.perf_counter()
    send_keys("{ESC}")
    t_esc = time.perf_counter() - t3
    print(f"Esc dismiss:   {t_esc * 1000:6.0f}ms")

    print(f"TOTAL:         {(time.perf_counter() - t0) * 1000:6.0f}ms")


if __name__ == "__main__":
    main()
