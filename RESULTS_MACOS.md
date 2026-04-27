# BotCity Desktop POC — Todoist (macOS)

Reference: macOS Accessibility API via [pyobjc](https://pyobjc.readthedocs.io/) (`AppKit`, `ApplicationServices`, `Quartz`).

## What this POC does

Skips BotCity's framework wrapper and talks directly to the macOS Accessibility (AX) API to:

1. Launch the Todoist Electron app (`/Applications/Todoist.app`).
2. Resolve its PID via `NSWorkspace.runningApplications()` filtered by bundle ID `com.todoist.mac.Todoist`.
3. Attach with `AXUIElementCreateApplication(pid)`.
4. **Force Chromium/Electron to publish its AX tree** by setting `AXManualAccessibility=True` on the app element.
5. Walk the entire AX tree and dump every control to disk.

Each stage is timed with `time.perf_counter()`.

## Setup

```
uv sync
```

Grant Accessibility access to whatever terminal you run from:
**System Settings → Privacy & Security → Accessibility →** add Terminal / iTerm / VS Code.

Run:

```
uv run python macos_poc_todoist.py
```

## Timings (warm run — Todoist already running)

| Stage         | Call                                                                                |       Time |
| ------------- | ----------------------------------------------------------------------------------- | ---------: |
| Launch        | `subprocess.Popen(["open", "-a", "Todoist"])`                                       |    0.00 s  |
| Find PID      | poll `NSWorkspace.runningApplications()` filtered by bundle ID                      |    0.00 s  |
| Attach        | `AXUIElementCreateApplication` + `AXManualAccessibility=True` + 1 s settle          |    1.05 s  |
| **Dump tree** | recursive DFS over `AXChildren`, format as `role title= desc= rect=…`               | **0.13 s** |
| **Total**     |                                                                                     | **1.18 s** |

**Tree size:** 558 lines / ~40 KB / 558 elements (`AXGroup`, `AXButton`, `AXStaticText`, `AXLink`, `AXTextField`, …) with role, title, description, value, and absolute screen rects. Exact count fluctuates ~±5% with what's currently rendered (visible task list, expanded sections).

## Speed notes

- **~1 s of "Attach" is a deliberate sleep** so Chromium can rebuild its AX tree after `AXManualAccessibility` flips. The actual pyobjc calls are sub-50 ms; the rest is Electron repopulating.
- **A targeted DFS is near-instant** (~5 ms in POC #2) — no need to walk all ~560 elements unless you want the full dump.
- AX traversal scales linearly with `AXChildren` count and is much cheaper than UIA on Windows for the same app (see comparison below).

## Gotchas worth keeping

1. **Electron / Chromium hides its AX tree by default.** Without intervention, `AXChildren` of Todoist's window returns **10** generic, unlabeled elements (`AXGroup`, anonymous `AXButton`s). Set `AXUIElementSetAttributeValue(app_ref, "AXManualAccessibility", True)` right after `AXUIElementCreateApplication` and sleep ~1 s — tree expands to **~560** elements with real titles. Same gate applies to VS Code, Slack, Discord, Cursor, anything Chromium-based.
2. **`AXPosition` / `AXSize` are not Python objects.** They come back as opaque `AXValueRef` wrappers. Unwrap with `AXValueGetValue(ref, kAXValueCGPointType, None)` (returns `(ok, CGPoint)`); attempting `.x` directly raises `AttributeError: 'AXValueRef' object has no attribute 'x'`.
3. **`NSApplicationActivateIgnoringOtherApps`** is a module-level constant in `AppKit`, not an attribute on `NSRunningApplication`. Use `from AppKit import NSApplicationActivateIgnoringOtherApps` and pass it to `app.activateWithOptions_(...)`.
4. **`AXWindows` returns an empty array if the app is hidden.** `open -a Todoist` re-shows it but you still need to activate (`app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)`) and wait briefly before AX queries succeed.
5. **Accessibility permissions are required.** Without them `AXIsProcessTrusted()` is `False` and every AX call no-ops silently. The permission attaches to the *binary that's running*, so granting it to Terminal does not cover iTerm and vice versa.
6. **Match on bundle ID, not localized name.** `app.bundleIdentifier() == "com.todoist.mac.Todoist"` is stable across locales and survives renaming.
7. **`AXTitle` ≠ `AXDescription`.** Some Electron buttons have only a description (icon-only buttons), some only a title. Concatenate both before string-matching.

## POC #2 — Click ONE "Add task" button without dumping the tree

Approach: depth-first search that returns the first element with `AXRole == "AXButton"` and `"add task" / "add" / "new task"` in its title or description. macOS analog of pywinauto's lazy `child_window(found_index=0)`. Click via `AXUIElementPerformAction(btn, "AXPress")`. Dismiss via a synthesised Esc key (Quartz `CGEventCreateKeyboardEvent`).

| Stage                                                       |          Time |
| ----------------------------------------------------------- | ------------: |
| Attach (launch + `AXManualAccessibility` + activate + 1 s) |       1,108 ms |
| Locate button (lazy DFS)                                    |     **5 ms**   |
| Click (`AXPress`)                                           |         0 ms   |
| Esc dismiss                                                 |        59 ms   |
| **TOTAL**                                                   | **1,328 ms**   |

**Locate is ~100× faster than the tree-walk.** Script: `macos_poc_click_one.py`. First match: `'Add task'` at `(12,143 224x34)` — the sidebar toolbar button.

## POC #3 — Click EVERY "Add task" button (single DFS, batch click)

Single DFS pass collects every matching button; then click each, sleep 150 ms, Esc, sleep 50 ms.

|                                                                           |        Time |
| ------------------------------------------------------------------------- | ----------: |
| Attach                                                                    |    1,070 ms |
| Find buttons (single DFS)                                                 |       87 ms |
| Click `[0]` — toolbar (12,143 224x34)                                     |      177 ms |
| Click `[1]` — inline (468,911 779x33)                                     |      153 ms |
| Click `[2]` — collapsed inline (468,956 779x0)                            |      153 ms |
| Click `[3]` — collapsed inline (468,956 779x0)                            |      154 ms |
| **Sweep total**                                                           |  **848 ms** |
| **GRAND TOTAL**                                                           | **2,005 ms** |

Per-button average **~159 ms**, dominated by the 150 ms inter-cycle sleep.

**Real button count = 4 in AX**, but two have `height=0` — collapsed/inline placeholders the AX tree still exposes. Filter on `AXSize.height > 0` if that's noise; the visible count drops to 2.

Script: `macos_poc_click_each_index.py`.

## POC #4 — `descendants` scan (full enumerate then filter)

Full enumeration of the AX tree, then filter by role + label. macOS analog of pywinauto's `descendants(control_type="Button")`. Intentionally slower than POC #3 — useful as a baseline.

| Stage                                                                       |       Time |
| --------------------------------------------------------------------------- | ---------: |
| Attach                                                                      |    1.07 s  |
| Full descendants scan                                                       |    0.08 s  |
| Sweep (4 clicks × ~162 ms)                                                  |    0.86 s  |
| **GRAND TOTAL**                                                             | **2.02 s** |

Counts: **596 total elements, 61 buttons, 4 targets.** Script: `macos_poc_click_addtask.py`.

### Speed comparison (within macOS)

| Approach                                              | Buttons clicked |    Total |
| ----------------------------------------------------- | --------------: | -------: |
| Tree dump (POC #1, no clicks)                         |               0 |   1.18 s |
| Single click via lazy DFS (POC #2)                    |               1 |   1.33 s |
| Iterate matches via single DFS (POC #3)               |               4 |   2.01 s |
| Full descendants scan + filter (POC #4)               |               4 |   2.02 s |

### Speed comparison vs Windows (same Todoist app)

| Stage                            | macOS (AX) | Windows (UIA, see RESULTS.md) |
| -------------------------------- | ---------: | ----------------------------: |
| Launch + attach                  |     1.05 s |                        1.18 s |
| Tree dump                        |     0.13 s |                       10.97 s |
| Single-click locate              |       5 ms |                        675 ms |
| Single-click total               |     1.33 s |                        2.40 s |
| Iterate-and-click total          |     2.01 s |                        5.28 s |

The macOS Accessibility API is **dramatically faster than UIA** for this workload. UIA's cost scales with descendant count (Electron exposes ~1,500 nodes on Windows); AX's tree is lazy but flat once realised, and the Chromium accessibility implementation is more compact than the UIA bridge.

### Levers if you need it faster

1. **Drop or shorten the 1 s post-`AXManualAccessibility` sleep.** Poll `AXChildren` count instead — exit once it stops growing (typically 200–400 ms).
2. **Drop the 150 ms inter-click sleep** if you don't need the modal to fully open/close.
3. **Pre-filter zero-height matches** in POC #3/#4 to skip 2 redundant click cycles.
4. **Cache the located button** if you'll be clicking the same one repeatedly — the AX element handle stays valid as long as the underlying control isn't destroyed.

## Files

- `macos_poc_todoist.py` — launch + attach + tree dump
- `macos_poc_click_one.py` — single click via lazy DFS
- `macos_poc_click_each_index.py` — single DFS, batch click
- `macos_poc_click_addtask.py` — descendants scan + filter
- `todoist_tree_macos.log` — captured AX tree (~560 lines)
- `pyproject.toml` / `uv.lock` — pinned env (`pyobjc-framework-*`)
