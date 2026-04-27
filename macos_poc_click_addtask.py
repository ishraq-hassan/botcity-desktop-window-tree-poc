"""
macOS Desktop POC #4: find every button in Reminders using a full
descendants scan (enumerate ALL controls, then filter by role+title).

This mirrors the approach of windows_poc_click_addtask.py which uses
pywinauto's descendants(control_type="Button") — intentionally slower
than a targeted DFS, useful as a baseline comparison.

Requirements:
    - macOS 12+
    - Grant Accessibility access to your terminal app:
      System Settings > Privacy & Security > Accessibility
"""

import subprocess
import sys
import time

from AppKit import NSRunningApplication, NSWorkspace
from ApplicationServices import (
    AXIsProcessTrusted,
    AXUIElementCopyAttributeValue,
    AXUIElementCreateApplication,
    AXUIElementPerformAction,
    kAXErrorSuccess,
)
from Quartz import CGEventCreateKeyboardEvent, CGEventPost, kCGHIDEventTap

APP_NAME = "Reminders"
APP_BUNDLE_ID = "com.apple.reminders"

TARGET_TERMS = ("add", "new reminder", "new item")


def _check_accessibility() -> None:
    if not AXIsProcessTrusted():
        print("ERROR: Accessibility access not granted.")
        print("Go to System Settings > Privacy & Security > Accessibility")
        print("and add your terminal application.")
        sys.exit(1)


def _ax_attr(element, attr):
    err, value = AXUIElementCopyAttributeValue(element, attr, None)
    return value if err == kAXErrorSuccess else None


def _format_rect(element) -> str:
    pos = _ax_attr(element, "AXPosition")
    size = _ax_attr(element, "AXSize")
    if pos is None or size is None:
        return ""
    return f"({pos.x:.0f},{pos.y:.0f} {size.width:.0f}x{size.height:.0f})"


def collect_all_descendants(element, results: list | None = None) -> list:
    """Walk the ENTIRE tree and return every element (unfiltered)."""
    if results is None:
        results = []
    results.append(element)
    for child in _ax_attr(element, "AXChildren") or []:
        collect_all_descendants(child, results)
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

    for app in NSWorkspace.sharedWorkspace().runningApplications():
        if app.bundleIdentifier() == APP_BUNDLE_ID:
            app.activateWithOptions_(NSRunningApplication.NSApplicationActivateIgnoringOtherApps)
            break
    time.sleep(0.3)

    windows = _ax_attr(app_ref, "AXWindows") or []
    if not windows:
        raise RuntimeError("No AX windows found for Reminders")
    main_window = windows[0]
    t_attach = time.perf_counter() - t0
    print(f"Attach (launch+focus):          {t_attach:6.2f}s")
    print(f"Window: {_ax_attr(main_window, 'AXTitle')!r}  rect={_format_rect(main_window)}")

    # --- Collect ALL descendants (full tree scan) ---
    t1 = time.perf_counter()
    all_elements = collect_all_descendants(main_window)
    t_scan = time.perf_counter() - t1

    # Filter to buttons only
    buttons = [e for e in all_elements if (_ax_attr(e, "AXRole") or "") == "AXButton"]

    # Filter to target buttons
    add_buttons = []
    for btn in buttons:
        title = (_ax_attr(btn, "AXTitle") or "").lower()
        desc = (_ax_attr(btn, "AXDescription") or "").lower()
        label = f"{title} {desc}"
        if any(term in label for term in TARGET_TERMS):
            add_buttons.append(btn)

    print(
        f"Find buttons (descendants scan): {t_scan:6.2f}s   "
        f"({len(all_elements)} total, {len(buttons)} buttons, {len(add_buttons)} target)"
    )

    if not add_buttons:
        print("No target buttons found — aborting.")
        return

    # --- Click each target button ---
    per_button = []
    sweep_start = time.perf_counter()
    for i, btn in enumerate(add_buttons, 1):
        rect = _format_rect(btn)
        title = _ax_attr(btn, "AXTitle") or ""
        desc = _ax_attr(btn, "AXDescription") or ""

        t_click_start = time.perf_counter()
        try:
            AXUIElementPerformAction(btn, "AXPress")
        except Exception as exc:
            print(f"  [{i}/{len(add_buttons)}] click failed: {exc!r}")
            continue
        t_clicked = time.perf_counter() - t_click_start

        time.sleep(0.15)

        t_esc_start = time.perf_counter()
        press_escape()
        t_esc = time.perf_counter() - t_esc_start

        cycle = time.perf_counter() - t_click_start
        per_button.append(cycle)
        print(
            f"  [{i}/{len(add_buttons)}] title={title!r} desc={desc!r} rect={rect}  "
            f"click={t_clicked * 1000:6.0f}ms  esc={t_esc * 1000:5.0f}ms  "
            f"cycle={cycle * 1000:6.0f}ms"
        )

        time.sleep(0.05)

    t_sweep = time.perf_counter() - sweep_start

    print()
    print(f"Sweep total:   {t_sweep:6.2f}s   ({len(per_button)} buttons cycled)")
    if per_button:
        avg = sum(per_button) / len(per_button)
        print(
            f"Per-button avg: {avg * 1000:5.0f}ms   "
            f"min={min(per_button) * 1000:5.0f}ms   max={max(per_button) * 1000:5.0f}ms"
        )
    print(f"GRAND TOTAL:   {time.perf_counter() - t0:6.2f}s")


if __name__ == "__main__":
    main()
