# BotCity Desktop Window Tree POC

Proof-of-concept scripts exploring [BotCity](https://botcity.dev/)'s desktop automation framework for interacting with Windows UIA controls in Electron apps — using **Todoist** as the target application.

## Overview

This POC evaluates the feasibility and performance of three approaches for locating and interacting with UI controls in an Electron application via the Windows UIA (UI Automation) backend:

| POC | Script | Approach | Result |
|-----|--------|----------|--------|
| **#1** | `poc_todoist.py` | Full UIA tree dump | ~12 s — 1,473 controls enumerated |
| **#2** | `poc_click_one.py` | Lazy `child_window()` lookup — click first match | ~2.4 s total |
| **#3** | `poc_click_each_index.py` | Iterate `found_index` — click every match | ~5.3 s for 2 buttons |
| **#4** | `poc_click_addtask.py` | `descendants()` scan + click all matches | ~13 s estimated |

> **Key takeaway:** Targeted `child_window()` lookups are **5×** faster than a full tree walk. The 11 s tree-dump cost is pywinauto/UIA, not BotCity — Electron exposes every DOM node as a control.

## Prerequisites

- **Windows 10/11** (UIA backend is Windows-only)
- **Python 3.10+**
- **Todoist desktop app** installed (`Todoist.exe`)

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

```bash
# POC #1 — Launch Todoist, attach via UIA, dump the full control tree
uv run python poc_todoist.py

# POC #2 — Click ONE "Add task" button (lazy lookup, no tree walk)
uv run python poc_click_one.py

# POC #3 — Click EVERY "Add task" button by iterating found_index
uv run python poc_click_each_index.py

# POC #4 — Click every "Add task" button via descendants() scan
uv run python poc_click_addtask.py
```

> **Note:** Update `APP_PATH` in each script to match your local Todoist installation path.

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

1. **Todoist's window title is dynamic** — it reflects the active view (`"Today"`, `"Inbox"`, project names). Match on `class_name="Chrome_WidgetWin_1"` + process PID instead.
2. **`bot.find_app_window()` is unreliable** for Electron apps — it doesn't poll long enough. Direct `pywinauto.Desktop()` polling works.
3. **`UIAWrapper` ≠ `WindowSpecification`** — `print_control_identifiers` lives on `WindowSpecification`. Wrap the handle: `Desktop(backend="uia").window(handle=w.handle)`.
4. **`print_control_identifiers(filename=...)` crashes on Unicode** — it opens files as cp1252. Redirect stdout into `StringIO`, then write UTF-8.

## Project Structure

```
├── poc_todoist.py            # POC #1 — tree dump
├── poc_click_one.py          # POC #2 — single click
├── poc_click_each_index.py   # POC #3 — iterate found_index
├── poc_click_addtask.py      # POC #4 — descendants() scan
├── RESULTS.md                # Detailed benchmark results & analysis
├── pyproject.toml            # Project config (uv, ruff, black, isort, pyright)
├── .pre-commit-config.yaml   # Pre-commit hook definitions
└── .python-version           # Pinned Python version
```

## License

Internal use only.
