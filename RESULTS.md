# BotCity Desktop POC — Todoist (Windows)

Reference: https://documentation.botcity.dev/frameworks/desktop/windows-apps/

## What this POC does

Uses BotCity's `botcity-framework-core` to:

1. Launch the Todoist Electron app (`Todoist.exe`).
2. Attach to it with the **UIA** backend (`Backend.UIA`).
3. Locate the main window (Electron uses `Chrome_WidgetWin_1` as class).
4. Walk the entire UIA tree and dump every control to disk.

Each stage is timed with `time.perf_counter()`.

## Setup

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install botcity-framework-core psutil
```

Run:

```
.venv/Scripts/python.exe poc_todoist.py
```

## Timings (warm run — Todoist already in tray)

| Stage         | Call                                                                                           |        Time |
| ------------- | ---------------------------------------------------------------------------------------------- | ----------: |
| Launch        | `bot.execute(APP_PATH)`                                                                        |      0.06 s |
| Connect       | `bot.connect_to_app(Backend.UIA, path=…)`                                                      |      0.72 s |
| Find window   | poll `Desktop(backend="uia").windows(class_name="Chrome_WidgetWin_1")` filtered by Todoist PID |      0.40 s |
| **Dump tree** | `WindowSpecification.print_control_identifiers()`                                              | **10.97 s** |
| **Total**     |                                                                                                | **12.16 s** |

**Tree size:** 1,473 lines / ~113 KB / hundreds of controls (Panes, Documents, Hyperlinks, Buttons, MenuItems, GroupBoxes, Images) with rectangles, `control_type`, `auto_id`, and ready-to-paste `child_window(...)` selectors.

## Speed notes

- **The 11 s dump cost is pywinauto / UIA, not BotCity.** UIA traversal of an Electron app is slow because every DOM node gets exposed as a control. If you only need a subtree, pass `depth=N` to `print_control_identifiers` or query specific controls via `bot.find_app_element(...)` — those are near-instant.
- Launch + connect + find-window is **~1.2 s** end-to-end; cold launch (Todoist not yet running) adds a few seconds for Electron startup.

## Gotchas worth keeping

1. **Todoist's window title is the active view name** (`'Today'`, `'Inbox'`, project names), not `"Todoist"`. Don't match on title — match on `class_name="Chrome_WidgetWin_1"` plus the process exe path. The script uses `psutil` to enumerate Todoist PIDs and filters windows by that.
2. **`bot.find_app_window(...)` returned `None`** during attach (the documented helper in BotCity for this) — it doesn't poll long enough for first-launch Electron windows. Direct `pywinauto.Desktop(...)` polling worked.
3. **`UIAWrapper` ≠ `WindowSpecification`.** `print_control_identifiers` lives on `WindowSpecification`, so wrap the found handle: `Desktop(backend="uia").window(handle=w.handle)`.
4. **`print_control_identifiers(filename=...)` opens the file as cp1252** and crashes on Unicode (Todoist has Arabic/emoji task names). Workaround: redirect stdout into a `StringIO`, then write UTF-8 yourself.

## POC #2 — Click ONE "Add task" button without dumping the tree

Approach: lazy `child_window(title="Add task", control_type="Button", found_index=0)`. UIA short-circuits on the first match instead of walking every descendant.

| Stage                                           |         Time |
| ----------------------------------------------- | -----------: |
| Attach (launch + connect + find window + focus) |     1,104 ms |
| Locate button (lazy `child_window` lookup)      |   **675 ms** |
| Click                                           |       264 ms |
| Esc dismiss                                     |        51 ms |
| **TOTAL**                                       | **2,403 ms** |

**~5× faster than the tree-walk approach.** Script: `poc_click_one.py`.

Gotcha: the bare lookup raised `ElementAmbiguousError` — there are 2 matches (toolbar + inline). Pass `found_index=0` to disambiguate.

## POC #3 — Click EVERY "Add task" button (iterate `found_index`)

Loop `found_index = 0, 1, 2, …` until the lookup times out. Each iteration: locate → click → 150 ms wait → Esc.

|                                                   |                                        Time |
| ------------------------------------------------- | ------------------------------------------: |
| Attach                                            |                                    1,189 ms |
| Click `[0]` — toolbar (rect 2572,89 → 2796,123)   |  1,308 ms (locate 840 + click 267 + esc 51) |
| Click `[1]` — inline (rect 3248,1021 → 4027,1055) | 1,515 ms (locate 1045 + click 270 + esc 51) |
| Probe `[2]` — 1 s timeout miss                    |                                    1,068 ms |
| **Sweep total**                                   |                                **4,091 ms** |
| **GRAND TOTAL**                                   |                                **5,280 ms** |

Per-button average **~1.4 s**, dominated by the lazy locate (~900 ms each).

**Real button count = 2.** The other "Add task" entries visible in the tree dump are text fragments inside the Document hyperlinks, not actual `Button` controls.

Script: `poc_click_each_index.py`.

### Speed comparison

| Approach                                                    | Buttons clicked |           Total |
| ----------------------------------------------------------- | --------------: | --------------: |
| Tree dump (POC #1, no clicks)                               |               0 |         12.16 s |
| Single click via `child_window` (POC #2)                    |               1 |          2.40 s |
| Iterate `found_index` (POC #3)                              |               2 |          5.28 s |
| `descendants(control_type="Button")` filter (earlier draft) |               2 | ~13 s estimated |

### Levers if you need it faster

1. **One UIA query, click all** — call `findwindows.find_elements(...)` once, click every result. Avoids re-searching per index.
2. **Skip the terminal timeout** — known count up front (option 1) means no 1 s probe at the end.

## Files

- `poc_todoist.py` — launch + attach + tree dump
- `poc_click_one.py` — single click without tree walk
- `poc_click_each_index.py` — iterate `found_index` to click every match
- `todoist_tree.log` — captured UIA tree (1,473 lines)
- `.venv/` — isolated env with `botcity-framework-core`, `pywinauto`, `psutil`
