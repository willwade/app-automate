# New App Guide

This is the shortest path for building a profile for a new app.

## Choosing a Strategy

app-automate supports multiple strategies for controlling apps. Pick the one that fits your app best:

| Strategy | Best for | Commands |
|---|---|---|
| **Keyboard shortcuts** | Apps with well-documented shortcuts | `extract-shortcuts` |
| **Accessibility** (AX/UIA/AT-SPI) | Apps with rich accessibility trees | `ax-list`, `uia-list`, `atspi-list` |
| **CDP** (Chrome DevTools Protocol) | Chromium-based browsers and Electron apps | `cdp-list`, `cdp-click` |
| **Computer vision** | Apps with no shortcuts and poor accessibility | `train`, `click` |

You can combine strategies in a single profile — see `examples/profiles/firefox/profile.json` for a profile that mixes shortcuts with other backends.

## Before You Start

- Make sure the target app is visible on screen and not minimized.
- On macOS, make sure `Screen Recording` is enabled for the process running this tool.
- If you plan to click later, also enable `Accessibility`.
- Create `app-automate.settings.toml` if you want to use the LLM-backed builder.

## Keyboard Shortcuts

Extract shortcuts from files, desktop environments, or the built-in ShortcutMapper data:

```bash
uv run app-automate extract-shortcuts "Firefox" --source file --shortcuts-file my-shortcuts.json
uv run app-automate extract-shortcuts "Firefox" --source desktop
uv run app-automate extract-shortcuts "" --source gnome-wm

# macOS: extract from live app menus and preferences
uv run app-automate extract-shortcuts Safari --source ax-menu
uv run app-automate extract-shortcuts Safari --source plist
uv run app-automate extract-shortcuts "" --source system-hotkeys
```

See `examples/profiles/firefox/profile.json` and `examples/profiles-imported/` for shortcut-based profile examples.

## Accessibility

For apps that expose useful accessibility metadata:

**macOS:**
```bash
uv run app-automate ax-list --app "Pages" --actionable-only
uv run app-automate ax-click --app "Pages" --contains "Insert" --max-depth 2 --dry-run
```

**Linux:**
```bash
uv run app-automate atspi-list --app "Calculator" --actionable-only
uv run app-automate atspi-click --app "Calculator" --contains "5" --dry-run
```

**Windows:**
```bash
uv run app-automate uia-list --app "Calculator" --actionable-only
uv run app-automate uia-click --app "Calculator" --contains "5" --dry-run
```

If that returns useful labels and bounds for the controls you care about, the app works well with the accessibility backend.

If accessibility returns very little or only generic controls, try another strategy.

## Chrome DevTools Protocol (CDP)

For Chromium-based browsers and Electron apps:

```bash
uv run app-automate cdp-setup
uv run app-automate cdp-list --actionable-only
uv run app-automate cdp-click --contains "Submit" --dry-run
```

## Computer Vision (Visual Profiles)

When other strategies don't cover what you need, use the visual profile flow.

1. Open the target app and put it in a stable state.
   Good examples:
   - the main screen is visible
   - important toolbar buttons are showing
   - temporary popovers are closed unless you are specifically training that mode

2. Run training against the live app window.

```bash
uv run app-automate train --app "Pages" --settings app-automate.settings.toml --output-dir examples/profiles/pages
```

3. Inspect the generated files in the output directory.
   Important files:
   - `profile.json`
   - `anchor_primary.png`
   - `anchor_secondary.png` if present
   - `anchor_review.json`
   - `anchor_review.png`
   - `mapping_error.txt` if training failed

4. If training succeeds, inspect the profile.

```bash
uv run app-automate inspect examples/profiles/pages/profile.json
uv run app-automate list-elements examples/profiles/pages/profile.json
```

5. Before clicking anything, verify runtime detection.

```bash
uv run app-automate locate-anchors --profile examples/profiles/pages/profile.json
uv run app-automate debug-target "insert" --profile examples/profiles/pages/profile.json --output-dir debug-output/pages
```

6. Only after that, try a real click.

```bash
uv run app-automate click "insert" --profile examples/profiles/pages/profile.json
```

### If Training Fails

Check:
- `mapping_error.txt`
- `mapping_output.attempt-1.json`
- `mapping_output.attempt-2.json`

Common failure causes:
- the model picked a repeated tile or generic area as an anchor
- the model used an invalid layout name
- the window is in a mode with too many repeated controls
- the proposed anchor crop is too large or not visually unique

The simplest fix is usually to retrain from a cleaner screen state with fewer repeated controls visible.

### Manual Review

If you want to review anchors interactively after a successful training run:

```bash
uv run app-automate train --app "Pages" --settings app-automate.settings.toml --output-dir examples/profiles/pages --review
```

That will:
- show the selected anchor review files
- ask whether to accept the chosen anchors
- let you enter replacement crop boxes as `x,y,width,height`

### How To Pick a Good Screen State

Prefer screens where:
- the app title bar or toolbar is visible
- important controls are persistent
- the UI is not dominated by repeated content cards or tiles

Avoid:
- search results grids
- galleries of repeated thumbnails
- temporary menus unless the menu itself is the target workflow

## Live Element Search

Search the live accessibility tree without building a profile. Works on all platforms (AX on macOS, UIA on Windows, AT-SPI on Linux). Synonym expansion means you can find elements even when you don't know the exact label.

```bash
# Find elements by label
uv run app-automate search "share" --app Safari

# Filter by role (button, link, textfield, menuitem, checkbox, etc.)
uv run app-automate search "email" --app Safari --role textfield

# Synonym search: "erase" finds "delete", "btn" finds buttons, etc.
uv run app-automate search "erase" --app TextEdit --all

# Click the top result
uv run app-automate search "reload" --app Safari --click --execute

# Type into a found text field
uv run app-automate search "email" --app Safari --type "hello@example.com" --execute

# JSON output for scripting
uv run app-automate search "back" --app Safari --json
```

Options:
- `--role <role>` — filter by element role (button, link, textfield, etc.)
- `--click` — click the top-ranked result
- `--type <text>` — type text into the top-ranked result
- `--index <n>` — act on the nth result (default: 1)
- `--dry-run/--execute` — preview or execute (default: dry-run)
- `--actionable/--all` — only actionable elements or all
- `--max-depth <n>` — accessibility tree depth (default: 10)
- `--max-results <n>` — maximum results (default: 20)
- `--json/--text` — output format

## Platform Notes

**Linux:** AT-SPI (`atspi-list`), keyboard shortcuts, CDP, and visual profiles all work. See `docs/linux-integration.md` for setup.

**Windows:** UIA (`uia-list`), keyboard shortcuts, CDP, and visual profiles all work. See `docs/windows-integration.md`.

**macOS:** AX (`ax-list`), keyboard shortcuts, CDP, and visual profiles all work. Native `axtool` Swift CLI provides fast accessibility operations. Extract shortcuts from live menus (`--source ax-menu`), app preferences (`--source plist`), or system hotkeys (`--source system-hotkeys`).

**Cross-platform:** Keyboard shortcuts and CDP work consistently across platforms. Accessibility and visual profiles are platform-specific.
