# Linux Integration

## Current Status

As of 2026-06-03, the Linux path is implemented and tested on Debian/Raspberry Pi OS:

- AT-SPI accessibility backend (`linux_atspi.py`)
- Linux input adapter (`adapters/linux.py`)
- Window management via `xdotool` / `wmctrl`
- Keyboard shortcut extraction from AT-SPI menus, GNOME WM, .desktop files
- Cross-platform shortcut-based profiles (Firefox, Galculator)

Validated commands:

- `atspi-list` (requires running accessibility bus)
- `atspi-click` (requires running accessibility bus)
- `atspi-type` (requires running accessibility bus)
- `extract-shortcuts` (works without display)
- `probe` (AT-SPI detection)
- Keyboard shortcut profiles via `click` / `dry-run`

## Dependencies

```bash
# AT-SPI accessibility bindings
sudo apt install python3-gi gir1.2-atspi-2.0

# Window management (for app capture/activation)
sudo apt install xdotool wmctrl

# Python dependencies
uv sync
```

Note: the AT-SPI Python bindings (`gi.repository.Atspi`) are only available via system packages, not PyPI. They are imported at runtime only when needed — the shortcut and CV paths work without them.

## What Works

### Shortcuts (no display server required)

Keyboard shortcut profiles are fully cross-platform and work without AT-SPI or a running desktop:

```bash
uv run app-automate extract-shortcuts firefox --source file \
  --shortcuts-file examples/profiles/firefox/firefox-shortcuts.json

uv run app-automate dry-run "url_bar" --profile examples/profiles/firefox/profile.json
```

### AT-SPI (requires accessibility bus)

The AT-SPI backend requires `at-spi-bus-launcher` running, which means a desktop session:

```bash
# Check if accessibility bus is running
python3 -c "import gi; gi.require_version('Atspi','2.0'); from gi.repository import Atspi; print(Atspi.get_desktop(0).get_child_count())"
```

If this fails with "Couldn't connect to accessibility bus", AT-SPI commands will not work. The `probe` command will correctly report `atspi.available = false`.

Commands when bus is active:

```bash
uv run app-automate atspi-list --app "Calculator" --actionable-only --json
uv run app-automate atspi-click --app "Calculator" --contains "5" --dry-run
uv run app-automate atspi-type --app "TextEditor" --contains "Search" --text "hello" --execute
```

### Window capture

```bash
# Requires xdotool
uv run app-automate train --app "Calculator" --output-dir examples/profiles/calc
```

### Shortcut extraction sources

| Source | Needs desktop? | Command |
|--------|---------------|---------|
| `.desktop` files | No | `--source desktop` |
| GNOME WM keybindings | No (just gsettings) | `--source gnome-wm` |
| AT-SPI menu accelerators | Yes | `--source atspi-menu` |
| User-provided JSON/TXT | No | `--source file --shortcuts-file X` |

## Backend Strategy on Linux

Pick the strategy that fits the app:

| Strategy | Best for |
|---|---|
| **Keyboard shortcuts** | Apps with well-documented shortcuts |
| **AT-SPI** | Apps with good accessibility trees (GTK/Qt, GNOME apps) |
| **CDP** | Chromium-based browsers and Electron apps |
| **Computer vision** | Apps with poor accessibility (some Electron apps, Wine apps, games) |

You can combine strategies in a single profile — see `docs/schema-reference.md`.

## Known Limitations

### AT-SPI

- Requires a running accessibility bus (`at-spi-bus-launcher`). Not available in headless/SSH-only sessions.
- The Python bindings (`gi.repository.Atspi`) are not on PyPI — must be installed via system packages.
- Some apps (especially non-GTK) may expose sparse or inaccurate accessibility trees.
- Wayland: `xdotool` has limited support on pure Wayland. Use `ydotool` as a fallback for input. Window geometry queries may need `wlr-randr` or `gnome-randr`.

### Window capture

- `xdotool` may not find windows on Wayland compositors. Use X11 or check for `xwayland` compatibility.
- `mss` screen capture works on both X11 and Wayland but coordinate systems may differ.

### Input

- `pyautogui` works on X11. On Wayland, it may not have full input injection capability.
- For Wayland-native input, consider `ydotool` as a backend adapter.

## Validation Matrix

Minimum Linux matrix:

- Debian 13 / Ubuntu 24.04+ / Fedora 40+
- Display servers:
  - X11 (Xorg)
  - Wayland (Mutter / KWin)
- Desktop environments:
  - GNOME
  - KDE Plasma
  - XFCE
- App categories:
  - GNOME/GTK app with good accessibility (Calculator, Text Editor, Files)
  - Firefox (partial AT-SPI, good shortcut coverage)
  - App with poor accessibility (GIMP, some Electron apps)

Recommended validation apps:

- GNOME Calculator or Galculator (simple, good accessibility)
- Firefox (browser, shortcut-heavy)
- GNOME Files/Nautilus (file manager, moderate accessibility)
- GIMP (poor accessibility — CV candidate)

## Validation Steps

### Phase 1: Shortcut profiles (no desktop needed)

1. Install: `uv sync`
2. Extract shortcuts: `uv run app-automate extract-shortcuts firefox --source file --shortcuts-file X`
3. Load profile: `uv run app-automate list-elements examples/profiles/firefox/profile.json`
4. Dry-run: `uv run app-automate dry-run "url_bar" --profile examples/profiles/firefox/profile.json`

### Phase 2: AT-SPI inspection (requires desktop)

1. Install: `sudo apt install python3-gi gir1.2-atspi-2.0`
2. Verify bus: `python3 -c "import gi; gi.require_version('Atspi','2.0'); from gi.repository import Atspi; print('OK')"`
3. Probe: `uv run app-automate probe "Calculator"`
4. List: `uv run app-automate atspi-list --app "Calculator" --actionable-only`
5. Click: `uv run app-automate atspi-click --app "Calculator" --contains "5" --execute`

### Phase 3: Semantic profile training

1. Train: `uv run app-automate train --backend atspi --app "Calculator" --output-dir examples/profiles/calc`
2. Inspect: `uv run app-automate inspect examples/profiles/calc/profile.json`
3. Run: `uv run app-automate click "5" --profile examples/profiles/calc/profile.json`

### Phase 4: Visual profiles (requires LLM key)

1. Train: `uv run app-automate train --app "GIMP" --output-dir examples/profiles/gimp`
2. Validate anchors: `uv run app-automate locate-anchors --profile examples/profiles/gimp/profile.json`
3. Run: `uv run app-automate click "brush" --profile examples/profiles/gimp/profile.json`

## Code Areas

Linux-specific modules:

- `src/app_automate/accessibility/linux_atspi.py` — AT-SPI backend
- `src/app_automate/adapters/linux.py` — Linux input adapter
- `src/app_automate/builder/window_capture.py` — Linux window bounds/activation (xdotool/wmctrl)
- `src/app_automate/cli/_accessibility.py` — atspi-list/click/type commands
- `src/app_automate/cli/_probe.py` — AT-SPI probe detection
- `src/app_automate/shortcuts/` — shortcut extraction (partially Linux-specific)
- `src/app_automate/platform_utils.py` — platform detection, DPI handling

## Risks

- Wayland compatibility is untested. `xdotool` and `pyautogui` may not work on pure Wayland.
- AT-SPI trees vary widely between GTK versions and app implementations.
- `python3-gi` Atspi bindings are system packages, not pip-installable. This complicates virtualenv usage — `uv run` uses its own Python but `gi` is in the system Python. May need `--system-site-packages` or `PYTHONPATH` adjustments.
- GNOME has been moving toward stricter sandboxing (Flatpak), which may restrict AT-SPI access to sandboxed apps.
