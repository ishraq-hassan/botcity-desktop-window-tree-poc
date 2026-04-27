"""
BotCity Desktop POC: launch Todoist, attach via UIA backend, dump the
control tree, and time each stage.
"""

import contextlib
import io
import sys
import time
from pathlib import Path

import psutil
from botcity.core import Backend, DesktopBot
from pywinauto import Desktop

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

APP_PATH = r"C:\Users\ishra\AppData\Local\Programs\todoist\Todoist.exe"
LOG_FILE = Path(__file__).parent / "todoist_tree.log"


def main() -> None:
    bot = DesktopBot()

    t0 = time.perf_counter()
    try:
        bot.execute(APP_PATH)
    except Exception as exc:
        print(f"[warn] execute() raised {exc!r} — will try to attach anyway")
    t_launch = time.perf_counter() - t0
    print(f"Launch:           {t_launch:6.2f}s")

    t1 = time.perf_counter()
    bot.connect_to_app(Backend.UIA, path=APP_PATH, timeout=30)
    t_connect = time.perf_counter() - t1
    print(f"Connect (UIA):    {t_connect:6.2f}s")

    t2 = time.perf_counter()
    todoist_pids = {
        p.info["pid"]
        for p in psutil.process_iter(["pid", "exe"])
        if p.info.get("exe")
        and Path(p.info["exe"]).resolve() == Path(APP_PATH).resolve()
    }
    main_window = None
    deadline = time.perf_counter() + 30
    while time.perf_counter() < deadline:
        for w in Desktop(backend="uia").windows(
            class_name="Chrome_WidgetWin_1", visible_only=True
        ):
            try:
                if w.process_id() in todoist_pids and w.rectangle().width() > 0:
                    main_window = w
                    break
            except Exception:
                continue
        if main_window:
            break
        time.sleep(0.25)
    if main_window is None:
        raise RuntimeError("No visible Todoist window found within 30s")
    t_window = time.perf_counter() - t2
    print(
        f"Find main window: {t_window:6.2f}s   title={main_window.window_text()!r}  class={main_window.class_name()}"
    )

    t3 = time.perf_counter()
    window_spec = Desktop(backend="uia").window(handle=main_window.handle)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        window_spec.print_control_identifiers()
    LOG_FILE.write_text(buf.getvalue(), encoding="utf-8")
    t_tree = time.perf_counter() - t3

    size = LOG_FILE.stat().st_size
    with LOG_FILE.open(encoding="utf-8", errors="ignore") as f:
        lines = sum(1 for _ in f)

    print(
        f"Dump tree:        {t_tree:6.2f}s   -> {LOG_FILE.name} ({lines} lines, {size:,} bytes)"
    )
    print(f"TOTAL:            {time.perf_counter() - t0:6.2f}s")


if __name__ == "__main__":
    main()
