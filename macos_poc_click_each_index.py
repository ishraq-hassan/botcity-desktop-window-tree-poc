"""
macOS Desktop POC #3: find EVERY matching button in Todoist by walking
the tree once, then click each one and dismiss with Esc.

Equivalent of windows_poc_click_each_index.py — but instead of iterating
found_index (a pywinauto concept), we collect all matches in a single DFS
pass and click them sequentially.

Requirements:
    - macOS 12+
    - Grant Accessibility access to your terminal app:
      System Settings > Privacy & Security > Accessibility
"""

import subprocess
import sys
import time

from AppKit import NSApplicationActivateIgnoringOtherApps, NSWorkspace
from ApplicationServices import (
    AXIsProcessTrusted,
    AXUIElementCopyAttributeValue,
    AXUIElementCreateApplication,
    AXUIElementPerformAction,
    AXUIElementSetAttributeValue,
    AXValueGetValue,
    kAXErrorSuccess,
    kAXValueCGPointType,
    kAXValueCGSizeType,
)
from Quartz import CGEventCreateKeyboardEvent, CGEventPost, kCGHIDEventTap

APP_NAME = "Todoist"
APP_BUNDLE_ID = "com.todoist.mac.Todoist"

TARGET_ROLE = "AXButton"
TARGET_TERMS = ("add task", "add", "new task")


def _check_accessibility() -> None:
    if not AXIsProcessTrusted():
        print("ERROR: Accessibility access not granted.")
        print("Go to System Settings > Privacy & Security > Accessibility")
        print("and add your terminal application.")
        sys.exit(1)


def _ax_attr(element, attr):
    err, value = AXUIElementCopyAttributeValue(element, attr, None)
    return value if err == kAXErrorSuccess else None


def _matches(element) -> bool:
    role = _ax_attr(element, "AXRole") or ""
    if role != TARGET_ROLE:
        return False
    title = (_ax_attr(element, "AXTitle") or "").lower()
    desc = (_ax_attr(element, "AXDescription") or "").lower()
    label = f"{title} {desc}"
    return any(term in label for term in TARGET_TERMS)


def _format_rect(element) -> str:
    pos_ref = _ax_attr(element, "AXPosition")
    size_ref = _ax_attr(element, "AXSize")
    if pos_ref is None or size_ref is None:
        return ""
    ok_p, pos = AXValueGetValue(pos_ref, kAXValueCGPointType, None)
    ok_s, size = AXValueGetValue(size_ref, kAXValueCGSizeType, None)
    if not (ok_p and ok_s):
        return ""
    return f"({pos.x:.0f},{pos.y:.0f} {size.width:.0f}x{size.height:.0f})"


def find_all(element, results: list | None = None) -> list:
    """DFS — collect every element matching our criteria."""
    if results is None:
        results = []
    if _matches(element):
        results.append(element)
    for child in _ax_attr(element, "AXChildren") or []:
        find_all(child, results)
    return results


def press_escape() -> None:
    key_down = CGEventCreateKeyboardEvent(None, 53, True)
    CGEventPost(kCGHIDEventTap, key_down)
    key_up = CGEventCreateKeyboardEvent(None, 53, False)
    CGEventPost(kCGHIDEventTap, key_up)


def find_app_pid(bundle_id: str, timeout: float = 30) -> int:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        for app in NSWorkspace.sharedWorkspace().runningApplications():
            if app.bundleIdentifier() == bundle_id:
                return app.processIdentifier()
        time.sleep(0.25)
    raise RuntimeError(f"{bundle_id} not found within {timeout}s")


def main() -> None:
    _check_accessibility()

    # --- Attach ---
    t0 = time.perf_counter()
    subprocess.Popen(["open", "-a", APP_NAME])
    pid = find_app_pid(APP_BUNDLE_ID)
    app_ref = AXUIElementCreateApplication(pid)
    # Force Chromium/Electron apps to expose their full AX tree.
    AXUIElementSetAttributeValue(app_ref, "AXManualAccessibility", True)

    for app in NSWorkspace.sharedWorkspace().runningApplications():
        if app.bundleIdentifier() == APP_BUNDLE_ID:
            app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
            break
    time.sleep(1.0)

    windows = _ax_attr(app_ref, "AXWindows") or []
    if not windows:
        raise RuntimeError("No AX windows found for Todoist")
    main_window = windows[0]
    t_attach = time.perf_counter() - t0
    print(f"Attach: {t_attach * 1000:6.0f}ms")

    # --- Find all matching buttons (single DFS pass) ---
    t1 = time.perf_counter()
    buttons = find_all(main_window)
    t_find = time.perf_counter() - t1
    print(f"Find buttons (DFS): {t_find * 1000:6.0f}ms   ({len(buttons)} matches)")

    if not buttons:
        print("No matching buttons found — try adjusting TARGET_TERMS.")
        return

    # --- Click each button ---
    cycles = []
    sweep_start = time.perf_counter()
    for i, btn in enumerate(buttons):
        cycle_start = time.perf_counter()

        title = _ax_attr(btn, "AXTitle") or ""
        desc = _ax_attr(btn, "AXDescription") or ""
        rect = _format_rect(btn)

        t_click_start = time.perf_counter()
        AXUIElementPerformAction(btn, "AXPress")
        t_click = time.perf_counter() - t_click_start

        time.sleep(0.15)

        t_esc_start = time.perf_counter()
        press_escape()
        t_esc = time.perf_counter() - t_esc_start

        cycle = time.perf_counter() - cycle_start
        cycles.append(cycle)
        print(
            f"  [{i}] title={title!r} desc={desc!r} rect={rect}  "
            f"click={t_click * 1000:5.0f}ms  esc={t_esc * 1000:4.0f}ms  "
            f"cycle={cycle * 1000:5.0f}ms"
        )

        time.sleep(0.05)

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
