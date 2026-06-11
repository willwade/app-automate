# Windows Integration

## Current Status

As of 2026-06-03, Windows support includes:

- **UIA backend**: `uia-list`, `uia-click`, `uia-type` — live-tested against VS Code, classic Outlook, new Outlook
- **Shortcut profiles**: Per-platform keys (`keys`, `keys_windows`, `keys_macos`, `keys_linux`) work on Windows via the consumer SDK and CLI
- **Visual/CV backend**: Profile + anchor + CV flow for apps with poor accessibility
- **Profile validation**: `app-automate validate <profile>` checks profiles for issues
- **Consumer SDK**: Python + .NET SDKs for loading and executing profiles programmatically

The most reliable Windows typing path is direct UIA focus plus UIA `SendKeys`. Mouse-only typing through `pyautogui` is not reliable enough for Outlook compose fields.

## Architecture

Two backends on Windows:

1. **Semantic backend** — UI Automation when the target app exposes usable controls, names, roles, and bounds. Or keyboard shortcuts (cross-platform, no display needed beyond app focus).

2. **Visual backend** — Profile + anchor + CV flow when UIA is missing, incomplete, or badly labelled.

A single profile can **mix both**: shortcut elements for navigation (`ctrl+s`) and UIA elements for specific controls (`click "Send"`).

## What Already Transfers Cleanly

- Profile schema in `src/app_automate/config` (with per-platform key support)
- LLM builder flow in `src/app_automate/builder`
- Anchor scoring and profile validation
- Transform math in `src/app_automate/runner/transform.py`
- Element resolution and debug overlays
- `uv` / `ruff` / `pytest` project tooling
- Settings-file-based model configuration
- Shortcut extraction and profiles (cross-platform by design)
- Consumer SDK (Python + .NET)

## What's Implemented

### Windows semantic backend (`src/app_automate/accessibility/windows_uia.py`)

- Enumerate visible UIA elements for a target app/window
- Capture role, name, automation id, bounds, enabled state, control type
- Filtered query: `find_matching_elements(app_name, contains=..., control_type=...)`
- Action execution against matched elements (click, type via SendKeys)

### Windows execution adapter (`src/app_automate/adapters/windows_input.py`)

- Wraps `pyautogui` with DPI-aware coordinate handling
- Centralized via `platform_utils.py` for DPI awareness

### CLI commands (`src/app_automate/cli/_accessibility.py`)

- `uia-list --app "App Name" [--actionable-only] [--json]`
- `uia-click --app "App Name" --contains "Text" [--dry-run|--execute]`
- `uia-type --app "App Name" --contains "Field" --text "hello" [--execute]`

### Profile commands (`src/app_automate/cli/_profiles.py`)

- `train --backend uia --app "App" --output-dir my-profile` — build semantic profile from live app
- `validate <profile>` — check profile for issues
- `list-elements <profile>` — show profile contents
- `dry-run <cmd> --profile <path>` — preview without acting
- `click <cmd> --profile <path>` — execute action

## Still To Do

### Shortcut harvesting on Windows

- [ ] **UIA accelerator key extraction.** `UIA_AcceleratorKeyPropertyId` on menu items gives shortcut text (e.g. "Ctrl+S"). Write `extract-shortcuts --source uia`.
- [ ] **Registry shortcut harvesting.** Some apps store keyboard bindings in `HKCU\Software\<Vendor>`.
- [ ] **`.lnk` file parsing.** Parse `IShellLink::GetHotkey` for globally-registered app shortcuts.
- [ ] **MS Office ribbon shortcuts.** Office apps have "Key Tips" (Alt sequences). Investigate if UIA exposes these.

### Capture validation

- [ ] Validate `train --app ...` behavior on Windows
- [ ] Confirm `mss` plus input coordinates align at 100%, 125%, and 150% scale
- [ ] Validate on single-monitor and dual-monitor setups
- [ ] Test mixed-scale multi-monitor setups

### Live testing

- [ ] Build a real UIA profile for a Windows app (Calculator, Notepad, Word)
- [ ] Test hybrid profiles (shortcuts + UIA elements) on Windows
- [ ] Validate `probe` recommendation logic on Windows
- [ ] Test `whats-here` on Windows

## Validation Matrix

- Windows 11
- Display scale: 100%, 125%, 150%
- Monitor setups: single, dual
- App categories:
  - Native accessible app (Calculator, Notepad)
  - Electron app with partial UIA (VS Code)
  - App with poor/no UIA (test CV fallback)

## Risks Specific To Windows

- DPI scaling can desynchronize capture and input coordinates
- Some Electron apps expose partial or inconsistent UIA trees
- Some apps expose controls without useful labels
- Multi-monitor setups may shift coordinate origins or scaling unexpectedly
- `pyautogui` is acceptable for MVP input but should not be the final strategy without validation

## Code Areas

Modules for Windows work:

- `src/app_automate/accessibility/windows_uia.py` — UIA backend
- `src/app_automate/adapters/windows_input.py` — Windows input adapter
- `src/app_automate/platform_utils.py` — DPI awareness, platform detection
- `src/app_automate/cli/_accessibility.py` — `uia-*` commands
- `src/app_automate/cli/_profiles.py` — `train`, `validate`, profile commands
- `src/app_automate/consumer/` — Consumer SDK (cross-platform)

## Example: Classic Outlook Compose

Validated live against classic Outlook for Windows.

1. Inspect actionable controls:

```bash
uv run app-automate uia-list --app "Inbox-will.wade@thinksmartbox.com - Outlook" --max-depth 20 --actionable-only --json
```

2. Open a new draft:

```bash
uv run app-automate uia-click --app "Inbox-will.wade@thinksmartbox.com - Outlook" --contains "New Email" --max-depth 20 --execute
```

3. Type a subject:

```bash
uv run app-automate uia-type --app "Untitled - Message (HTML)" --contains "Subject" --control-type EditControl --max-depth 24 --text "Test Subject" --replace --execute
```

4. Type the message body:

```bash
uv run app-automate uia-type --app "Test Subject - Message (HTML)" --contains "Page 1 content" --control-type EditControl --max-depth 24 --text "Hello from app-automate on Windows." --replace --execute
```

Notes:

- The compose window title changes after the subject is entered.
- Outlook commits the subject once focus moves off the subject field.
- `--max-depth 20` / `--max-depth 24` needed for reliable discovery.
- Direct UIA invoke plus UIA `SendKeys` was reliable; generic mouse typing was not.
