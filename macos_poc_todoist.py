"""
macOS Desktop POC #1: launch Todoist, attach via the macOS
Accessibility API, walk the full AX tree, and dump every control to disk.
Times each stage with time.perf_counter().

Equivalent of windows_poc_todoist.py but using macOS Accessibility instead of
Windows UIA.

Requirements:
    - macOS 12+
    - Grant Accessibility access to your terminal app:
      System Settings > Privacy & Security > Accessibility
"""

import subprocess
import sys
import time
from pathlib import Path

from AppKit import NSApplicationActivateIgnoringOtherApps, NSWorkspace
from ApplicationServices import (
    AXIsProcessTrusted,
    AXUIElementCopyAttributeNames,
    AXUIElementCopyAttributeValue,
    AXUIElementCreateApplication,
    AXUIElementSetAttributeValue,
    AXValueGetValue,
    kAXErrorSuccess,
    kAXValueCGPointType,
    kAXValueCGSizeType,
)

APP_NAME = "Todoist"
APP_BUNDLE_ID = "com.todoist.mac.Todoist"
LOG_FILE = Path(__file__).parent / "todoist_tree_macos.log"


def _check_accessibility() -> None:
    """Exit early if Accessibility access hasn't been granted."""
    if not AXIsProcessTrusted():
        print("ERROR: Accessibility access not granted.")
        print("Go to System Settings > Privacy & Security > Accessibility")
        print("and add your terminal application.")
        sys.exit(1)


def _ax_attr(element, attr):
    """Return an AX attribute value, or None on error."""
    err, value = AXUIElementCopyAttributeValue(element, attr, None)
    return value if err == kAXErrorSuccess else None


def _ax_attrs(element):
    """Return the list of attribute names for an element."""
    err, names = AXUIElementCopyAttributeNames(element, None)
    return list(names) if err == kAXErrorSuccess and names else []


def _format_rect(element) -> str:
    """Return 'x,y wxh' from AXPosition + AXSize, or '' if unavailable."""
    pos_ref = _ax_attr(element, "AXPosition")
    size_ref = _ax_attr(element, "AXSize")
    if pos_ref is None or size_ref is None:
        return ""
    ok_p, pos = AXValueGetValue(pos_ref, kAXValueCGPointType, None)
    ok_s, size = AXValueGetValue(size_ref, kAXValueCGSizeType, None)
    if not (ok_p and ok_s):
        return ""
    return f"({pos.x:.0f},{pos.y:.0f} {size.width:.0f}x{size.height:.0f})"


def walk_tree(element, depth: int = 0, lines: list | None = None) -> list[str]:
    """Recursively walk the AX tree and collect one line per control."""
    if lines is None:
        lines = []

    role = _ax_attr(element, "AXRole") or ""
    title = _ax_attr(element, "AXTitle") or ""
    desc = _ax_attr(element, "AXDescription") or ""
    value = _ax_attr(element, "AXValue") or ""
    rect = _format_rect(element)

    indent = "  " * depth
    parts = [f"{indent}{role}"]
    if title:
        parts.append(f"title={title!r}")
    if desc:
        parts.append(f"desc={desc!r}")
    if value:
        val_str = str(value)[:80]
        parts.append(f"value={val_str!r}")
    if rect:
        parts.append(rect)

    lines.append("  ".join(parts))

    children = _ax_attr(element, "AXChildren") or []
    for child in children:
        walk_tree(child, depth + 1, lines)

    return lines


def find_app_pid(bundle_id: str, timeout: float = 30) -> int:
    """Poll NSWorkspace until the app with *bundle_id* is running."""
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        for app in NSWorkspace.sharedWorkspace().runningApplications():
            if app.bundleIdentifier() == bundle_id:
                return app.processIdentifier()
        time.sleep(0.25)
    raise RuntimeError(f"{bundle_id} not found within {timeout}s")


def main() -> None:
    _check_accessibility()

    # --- Launch ---
    t0 = time.perf_counter()
    subprocess.Popen(["open", "-a", APP_NAME])
    t_launch = time.perf_counter() - t0
    print(f"Launch:           {t_launch:6.2f}s")

    # --- Find PID ---
    t1 = time.perf_counter()
    pid = find_app_pid(APP_BUNDLE_ID)
    t_pid = time.perf_counter() - t1
    print(f"Find PID:         {t_pid:6.2f}s   (pid={pid})")

    # --- Create AX ref & get main window ---
    t2 = time.perf_counter()
    app_ref = AXUIElementCreateApplication(pid)
    # Force Chromium/Electron apps to expose their full AX tree.
    AXUIElementSetAttributeValue(app_ref, "AXManualAccessibility", True)
    time.sleep(1.0)
    windows = _ax_attr(app_ref, "AXWindows") or []
    if not windows:
        # Bring app to front and wait a moment
        for app in NSWorkspace.sharedWorkspace().runningApplications():
            if app.bundleIdentifier() == APP_BUNDLE_ID:
                app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                break
        time.sleep(1)
        windows = _ax_attr(app_ref, "AXWindows") or []

    if not windows:
        raise RuntimeError("No AX windows found for Todoist")

    main_window = windows[0]
    win_title = _ax_attr(main_window, "AXTitle") or "(untitled)"
    t_attach = time.perf_counter() - t2
    print(f"Attach (AX ref):  {t_attach:6.2f}s   window={win_title!r}")

    # --- Dump tree ---
    t3 = time.perf_counter()
    lines = walk_tree(main_window)
    LOG_FILE.write_text("\n".join(lines), encoding="utf-8")
    t_tree = time.perf_counter() - t3

    size = LOG_FILE.stat().st_size
    print(f"Dump tree:        {t_tree:6.2f}s   -> {LOG_FILE.name} ({len(lines)} lines, {size:,} bytes)")
    print(f"TOTAL:            {time.perf_counter() - t0:6.2f}s")


if __name__ == "__main__":
    main()
