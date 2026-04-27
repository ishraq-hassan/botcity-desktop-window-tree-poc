"""
macOS Desktop POC #2: click ONE button in Reminders without dumping the tree.
Uses a depth-first search that stops at the first match — the macOS equivalent
of pywinauto's lazy child_window() lookup.

Equivalent of windows_poc_click_one.py.

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

# Button to look for — "Add" is the toolbar "+" button in Reminders.
TARGET_ROLE = "AXButton"
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


def _matches(element) -> bool:
    """Return True if element is a button matching our target terms."""
    role = _ax_attr(element, "AXRole") or ""
    if role != TARGET_ROLE:
        return False
    title = (_ax_attr(element, "AXTitle") or "").lower()
    desc = (_ax_attr(element, "AXDescription") or "").lower()
    label = f"{title} {desc}"
    return any(term in label for term in TARGET_TERMS)


def _format_rect(element) -> str:
    pos = _ax_attr(element, "AXPosition")
    size = _ax_attr(element, "AXSize")
    if pos is None or size is None:
        return ""
    return f"({pos.x:.0f},{pos.y:.0f} {size.width:.0f}x{size.height:.0f})"


def find_first(element):
    """DFS — return the first matching element, or None."""
    if _matches(element):
        return element
    for child in _ax_attr(element, "AXChildren") or []:
        found = find_first(child)
        if found is not None:
            return found
    return None


def press_escape() -> None:
    """Synthesise an Escape key press via Quartz."""
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

    # Bring to front
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
    print(f"Attach:        {t_attach * 1000:6.0f}ms")

    # --- Locate first matching button (DFS) ---
    t1 = time.perf_counter()
    btn = find_first(main_window)
    t_locate = time.perf_counter() - t1

    if btn is None:
        print(f"Locate button: {t_locate * 1000:6.0f}ms   NOT FOUND")
        print("No matching button found — try adjusting TARGET_TERMS.")
        return

    rect = _format_rect(btn)
    title = _ax_attr(btn, "AXTitle") or ""
    desc = _ax_attr(btn, "AXDescription") or ""
    print(f"Locate button: {t_locate * 1000:6.0f}ms   title={title!r} desc={desc!r} rect={rect}")

    # --- Click via AXPress ---
    t2 = time.perf_counter()
    AXUIElementPerformAction(btn, "AXPress")
    t_click = time.perf_counter() - t2
    print(f"Click:         {t_click * 1000:6.0f}ms")

    # --- Dismiss with Esc ---
    time.sleep(0.15)
    t3 = time.perf_counter()
    press_escape()
    t_esc = time.perf_counter() - t3
    print(f"Esc dismiss:   {t_esc * 1000:6.0f}ms")

    print(f"TOTAL:         {(time.perf_counter() - t0) * 1000:6.0f}ms")


if __name__ == "__main__":
    main()
