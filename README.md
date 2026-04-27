# BotCity Desktop Window Tree POC

Proof-of-concept scripts exploring desktop UI automation using **accessibility trees** — comparing Windows UIA (via [BotCity](https://botcity.dev/) + pywinauto) with the native **macOS Accessibility API** (via pyobjc).

## Overview

This POC evaluates the feasibility and performance of four approaches for locating and interacting with UI controls via the platform's accessibility backend.

### Windows (Todoist — Electron app)

| POC | Script | Approach | Result |
|-----|--------|----------|--------|
| **#1** | `windows_poc_todoist.py` | Full UIA tree dump | ~12 s — 1,473 controls enumerated |
| **#2** | `windows_poc_click_one.py` | Lazy `child_window()` lookup — click first match | ~2.4 s total |
| **#3** | `windows_poc_click_each_index.py` | Iterate `found_index` — click every match | ~5.3 s for 2 buttons |
| **#4** | `windows_poc_click_addtask.py` | `descendants()` scan + click all matches | ~13 s estimated |

### macOS (Todoist — Electron app)

| POC | Script | Approach |
|-----|--------|----------|
| **#1** | `macos_poc_todoist.py` | Full AX tree dump to file |
| **#2** | `macos_poc_click_one.py` | DFS — stop at first match, click via `AXPress` |
| **#3** | `macos_poc_click_each_index.py` | Single DFS pass — collect all matches, click each |
| **#4** | `macos_poc_click_addtask.py` | Full descendants scan, filter, then click |

> **Key takeaway (Windows):** Targeted `child_window()` lookups are **5×** faster than a full tree walk. The 11 s tree-dump cost is pywinauto/UIA, not BotCity — Electron exposes every DOM node as a control.

## Prerequisites

### Windows
- **Windows 10/11** (UIA backend)
- **Python 3.10+**
- **Todoist desktop app** installed (`Todoist.exe`)

### macOS
- **macOS 12+**
- **Python 3.10+**
- **Todoist desktop app** installed
- **Accessibility access** granted to your terminal app:
  System Settings → Privacy & Security → Accessibility

## Setup

```bash
# Install uv (if not already installed)
# https://docs.astral.sh/uv/getting-started/installation/

# Create the virtual environment and install dependencies
uv sync

# Install pre-commit hooks
uv run pre-commit install
```

## Usage

### Windows

```bash
# POC #1 — Launch Todoist, attach via UIA, dump the full control tree
uv run python windows_poc_todoist.py

# POC #2 — Click ONE "Add task" button (lazy lookup, no tree walk)
uv run python windows_poc_click_one.py

# POC #3 — Click EVERY "Add task" button by iterating found_index
uv run python windows_poc_click_each_index.py

# POC #4 — Click every "Add task" button via descendants() scan
uv run python windows_poc_click_addtask.py
```

> **Note:** Update `APP_PATH` in each Windows script to match your local Todoist installation path.

### macOS

```bash
# POC #1 — Launch Todoist, walk the full AX tree, dump to file
uv run python macos_poc_todoist.py

# POC #2 — Click ONE "Add task" button (DFS, stop at first match)
uv run python macos_poc_click_one.py

# POC #3 — Click EVERY matching button (single DFS pass)
uv run python macos_poc_click_each_index.py

# POC #4 — Full descendants scan + filter + click all
uv run python macos_poc_click_addtask.py
```

> **Note:** On first run, macOS will prompt you to grant Accessibility access to your terminal.

## Development

This project uses modern Python tooling managed by [uv](https://docs.astral.sh/uv/):

| Tool | Purpose |
|------|---------|
| [uv](https://docs.astral.sh/uv/) | Package & project management |
| [Ruff](https://docs.astral.sh/ruff/) | Linting |
| [Black](https://black.readthedocs.io/) | Code formatting |
| [isort](https://pycqa.github.io/isort/) | Import sorting |
| [Pyright](https://github.com/microsoft/pyright) | Static type checking |
| [pre-commit](https://pre-commit.com/) | Git hook automation |

### Linting & Formatting

```bash
# Run all pre-commit hooks on all files
uv run pre-commit run --all-files

# Or run tools individually
uv run ruff check .                # lint
uv run ruff check . --fix          # lint + autofix
uv run black .                     # format
uv run isort .                     # sort imports
uv run pyright                     # type check
```

## Key Findings & Gotchas

### Windows (UIA / pywinauto)

1. **Todoist's window title is dynamic** — it reflects the active view (`"Today"`, `"Inbox"`, project names). Match on `class_name="Chrome_WidgetWin_1"` + process PID instead.
2. **`bot.find_app_window()` is unreliable** for Electron apps — it doesn't poll long enough. Direct `pywinauto.Desktop()` polling works.
3. **`UIAWrapper` ≠ `WindowSpecification`** — `print_control_identifiers` lives on `WindowSpecification`. Wrap the handle: `Desktop(backend="uia").window(handle=w.handle)`.
4. **`print_control_identifiers(filename=...)` crashes on Unicode** — it opens files as cp1252. Redirect stdout into `StringIO`, then write UTF-8.

### macOS (Accessibility API / pyobjc)

1. **Accessibility permissions are mandatory** — without them, `AXUIElementCopyAttributeValue` returns errors for every attribute. Grant access in System Settings → Privacy & Security → Accessibility.
2. **`AXUIElementPerformAction(element, "AXPress")` is the click equivalent** — no coordinate-based clicking needed.
3. **Native apps have much smaller AX trees** than Electron apps on Windows — expect significantly faster tree dumps.
4. **Keyboard events require Quartz CGEvents** — use `CGEventCreateKeyboardEvent` + `CGEventPost` for Escape/Enter key simulation.

## Project Structure

```
├── windows_poc_todoist.py          # Windows POC #1 — UIA tree dump (Todoist)
├── windows_poc_click_one.py        # Windows POC #2 — single click
├── windows_poc_click_each_index.py # Windows POC #3 — iterate found_index
├── windows_poc_click_addtask.py    # Windows POC #4 — descendants() scan
├── macos_poc_todoist.py            # macOS POC #1 — AX tree dump (Todoist)
├── macos_poc_click_one.py          # macOS POC #2 — DFS first match click
├── macos_poc_click_each_index.py   # macOS POC #3 — DFS all matches click
├── macos_poc_click_addtask.py      # macOS POC #4 — descendants scan
├── RESULTS.md                      # Detailed Windows benchmark results
├── pyproject.toml                  # Project config (uv, ruff, black, isort, pyright)
├── .pre-commit-config.yaml         # Pre-commit hook definitions
└── .python-version                 # Pinned Python version
```

## License

Internal use only.
