# app-automate

Control desktop applications programmatically — through keyboard shortcuts, accessibility APIs, browser DevTools, or visual template matching. Works on Linux, Windows, and macOS.

## How it works

You describe what you want to press or click in a JSON profile. `app-automate` finds the target and performs the action.

Four strategies, from simplest to most complex:

| Strategy | Needs display? | Cross-platform? | Reliability |
|----------|---------------|-----------------|-------------|
| **Shortcuts** | App must be focused | Yes | High — key combos don't change with screen size |
| **Accessibility** (AT-SPI / UIA / AX) | Yes | Per-platform | High — semantic tree doesn't shift |
| **CDP** | Yes | WebView2 only | High — DOM selectors |
| **Computer Vision** | Yes + screenshots | Yes | Medium — anchor images can break on resize/theme |

## Install

```bash
uv sync

# Linux: install AT-SPI bindings for accessibility support
sudo apt install python3-gi gir1.2-atspi-2.0 xdotool wmctrl
```

## 30-second example: Firefox with shortcuts

Create a profile with keyboard shortcuts — works across platforms:

```json
{
  "profile_id": "firefox",
  "app_name": "Firefox",
  "type": "semantic",
  "backend": "shortcut",
  "semantic_elements": {
    "new_tab": {
      "label": "new_tab",
      "aliases": ["open tab"],
      "action": "shortcut",
      "shortcut": {"keys": "ctrl+t", "keys_macos": "cmd+t", "description": "Open new tab"}
    },
    "url_bar": {
      "label": "url_bar",
      "aliases": ["address bar", "navigate"],
      "action": "shortcut",
      "shortcut": {"keys": "ctrl+l", "keys_macos": "cmd+l", "description": "Focus URL bar"}
    }
  }
}
```

Then use it:

```bash
# See what the profile contains
uv run app-automate list-elements examples/profiles/firefox/profile.json

# Preview without acting
uv run app-automate dry-run "url_bar" --profile examples/profiles/firefox/profile.json

# Actually execute (sends ctrl+l to focused Firefox window)
uv run app-automate click "url_bar" --profile examples/profiles/firefox/profile.json
```

## Strategies in detail

### 1. Shortcuts — the cross-platform default

If an app has keyboard shortcuts (most do), this is the easiest and most reliable approach. No screenshots, no accessibility trees, no screen coordinates.

**Import existing shortcuts from a file:**

```bash
# From a JSON file you wrote or copied from docs
uv run app-automate extract-shortcuts Firefox --source file \
  --shortcuts-file my-shortcuts.json

# From GNOME window manager bindings (Linux)
uv run app-automate extract-shortcuts "" --source gnome-wm

# From AT-SPI menu accelerators (Linux, requires running app)
uv run app-automate extract-shortcuts Firefox --source atspi-menu

# From .desktop files (Linux)
uv run app-automate extract-shortcuts firefox --source desktop
```

**Shortcut file format** (JSON):

```json
{
  "new_tab": {"keys": "ctrl+t", "description": "Open new tab"},
  "close_tab": {"keys": "ctrl+w", "description": "Close tab"},
  "find": {"keys": "ctrl+f", "description": "Find in page"}
}
```

**Or plain text** (`=` or `:` separated):

```
new_tab = ctrl+t
close_tab = ctrl+w
find = ctrl+f
```

### 2. Accessibility — semantic element targeting

Query the app's accessibility tree to find buttons, fields, and menus by name.

**Linux (AT-SPI):**
```bash
uv run app-automate atspi-list --app "Calculator" --actionable-only --json
uv run app-automate atspi-click --app "Calculator" --contains "5" --dry-run
uv run app-automate atspi-type --app "TextEditor" --contains "Search" --text "hello" --execute
```

**Windows (UIA):**
```bash
uv run app-automate uia-list --app "Calculator" --actionable-only
uv run app-automate uia-click --app "Calculator" --contains "Close" --execute
```

**macOS (AX):**
```bash
uv run app-automate ax-list --app "Pages" --actionable-only
uv run app-automate ax-click --app "Pages" --contains "Insert" --dry-run
```

**Build a semantic profile from the live app:**
```bash
uv run app-automate train --backend atspi --app "Calculator" --output-dir my-profile
uv run app-automate click "5" --profile my-profile/profile.json
```

### 3. CDP — WebView2 apps (Windows)

```bash
uv run app-automate cdp-setup --app "Outlook"
uv run app-automate cdp-list --actionable-only
uv run app-automate cdp-click --contains "New email" --execute
```

### 4. Visual profiles — anything else

For apps with poor accessibility support. Takes a screenshot, generates a grid overlay, uses an LLM to build a profile, then matches anchor images at runtime.

```bash
# Requires an OpenAI key in settings
uv run app-automate train --app "MyApp" --output-dir my-profile
uv run app-automate click "save_button" --profile my-profile/profile.json
```

## Discovering what's available

```bash
# Auto-detect best backend for an app
uv run app-automate probe "Calculator"

# See what elements are near your cursor
uv run app-automate whats-here --radius 150
```

## Profile structure

A profile is a `profile.json` file (plus optional anchor images for CV). **There is one schema.** Every profile can contain shortcuts, accessibility elements, and visual elements — mix and match as needed.

**`backend`** tells the runtime which primary strategy to use: `"shortcut"` (keyboard only), `"atspi"`/`"uia"`/`"ax"` (accessibility), `"cdp"` (browser), or `"mixed"` (hybrid). Per-element, each `action` determines what actually happens (shortcut, click, type, etc.).

**Example — Firefox with shortcuts + accessibility:**
```json
{
  "profile_id": "firefox",
  "app_name": "Firefox",
  "type": "semantic",
  "backend": "atspi",
  "shortcuts": {
    "new_tab": {"keys": "ctrl+t", "keys_macos": "cmd+t", "description": "Open new tab"},
    "close_tab": {"keys": "ctrl+w", "keys_macos": "cmd+w", "description": "Close tab"},
    "url_bar": {"keys": "ctrl+l", "keys_macos": "cmd+l", "description": "Focus URL bar"}
  },
  "semantic_elements": {
    "new_tab": {
      "label": "new_tab",
      "aliases": ["open tab"],
      "action": "shortcut",
      "shortcut": {"keys": "ctrl+t", "keys_macos": "cmd+t", "description": "Open new tab"}
    },
    "url_bar": {
      "label": "url_bar",
      "aliases": ["address bar", "navigate"],
      "action": "shortcut",
      "shortcut": {"keys": "ctrl+l", "keys_macos": "cmd+l", "description": "Focus URL bar"}
    },
    "search_box": {
      "label": "Search with Google",
      "role": "entry",
      "action": "type"
    }
  }
}
```

**Why mix?** Shortcuts are cross-platform and reliable (`ctrl+t` on Windows/Linux, `cmd+t` on macOS). Accessibility elements let you target specific UI that has no shortcut (like typing into a search box). Use shortcuts for the 80%, accessibility for the 20%. Per-platform keys (`keys_macos`, `keys_linux`, `keys_windows`) handle OS differences without separate files. It's all one profile.

**Actions available:** `click`, `double_click`, `right_click`, `type`, `drag`, `scroll`, `hotkey`, `wait`, `shortcut`.

## Adding a new app

1. **Check for shortcuts first.** Most apps document their keyboard shortcuts. Drop them in a JSON file and you're done. See `examples/profiles/` for hand-crafted profiles and `examples/profiles-imported/` for 20 auto-imported apps.

2. **Probe the app** to see if accessibility works:
   ```bash
   uv run app-automate probe "AppName"
   ```

3. **If accessibility looks good**, build a semantic profile:
   ```bash
   uv run app-automate train --backend atspi --app "AppName" --output-dir examples/profiles/appname
   ```

4. **If accessibility is poor**, try the CV path:
   ```bash
   uv run app-automate train --app "AppName" --output-dir examples/profiles/appname
   ```

5. **Mix strategies.** A single profile can contain shortcut elements AND accessibility elements. Use shortcuts for the reliable cross-platform actions (save, quit, new tab) and accessibility for everything else.

## Example profiles

**Hand-crafted** (`examples/profiles/`):

| Profile | Strategy | Notes |
|---------|----------|-------|
| Firefox | Shortcuts + AT-SPI | Hybrid: shortcuts for navigation, AT-SPI for UI |
| Chrome | Shortcuts | 34 cross-platform shortcuts |
| VS Code | Shortcuts | 38 cross-platform shortcuts |
| LibreOffice Writer | Shortcuts | 40 cross-platform shortcuts |
| Galculator | Keyboard shortcuts | Linux calculator |

**Auto-imported from ShortcutMapper** (`examples/profiles-imported/`): 20 apps including Blender (1,525), Photoshop (827), IntelliJ IDEA (465), and more. Run `app-automate validate examples/profiles-imported/<app>` to inspect any of them.

## Platform support

| Feature | Linux | Windows | macOS |
|---------|-------|---------|-------|
| Keyboard shortcuts | Yes | Yes | Yes |
| Visual profiles (CV) | Yes | Yes | Yes |
| Accessibility | AT-SPI | UIA | System Events |
| Browser/WebView | — | CDP | — |
| Window capture | xdotool + mss | user32 + mss | screencapture + mss |

## CLI Reference

### Discovery
| Command | Description |
|---------|-------------|
| `probe <app>` | Detect best backend for an app |
| `whats-here` | List elements near cursor |
| `extract-shortcuts <app>` | Extract keyboard shortcuts |

### Accessibility
| Command | Description |
|---------|-------------|
| `atspi-list --app <name>` | List elements via AT-SPI (Linux) |
| `atspi-click --app <name> --contains <text>` | Click via AT-SPI |
| `atspi-type --app <name> --contains <text> --text <text>` | Type via AT-SPI |
| `uia-list --app <name>` | List elements via UIA (Windows) |
| `uia-click --app <name> --contains <text>` | Click via UIA |
| `uia-type --app <name> --contains <text> --text <text>` | Type via UIA |
| `ax-list --app <name>` | List elements via AX (macOS) |
| `ax-click --app <name> --contains <text>` | Click via AX |

### CDP (WebView2)
| Command | Description |
|---------|-------------|
| `cdp-setup --app <name>` | Enable CDP debugging |
| `cdp-list` | List elements via DevTools |
| `cdp-click --contains <text>` | Click via DevTools |
| `cdp-type --contains <text> --text <text>` | Type via DevTools |

### Profiles
| Command | Description |
|---------|-------------|
| `train --backend <b> --app <name>` | Build semantic profile |
| `train --app <name>` | Build visual profile (needs LLM key) |
| `inspect <profile>` | Describe a profile |
| `list-elements <profile>` | List elements |
| `dry-run <cmd> --profile <path>` | Preview without acting |
| `click <cmd> --profile <path>` | Execute action |
| `locate-anchors --profile <path>` | Check anchor detection |
| `debug-target <cmd> --profile <path>` | Generate debug overlay |

### Common options
- `--dry-run` / `--execute` — preview vs real input
- `--actionable-only` / `--all` — filter to interactive controls
- `--json` / `--table` — output format
- `--index <n>` — select among multiple matches (1-based)
- `--exact` / `--substring` — matching mode

## Development

```bash
uv sync
uv run ruff check .
uv run ruff format .
uv run pytest
```

## Documentation

- **[Profile Schema Reference](docs/schema-reference.md)** — complete field reference with examples
- [Architecture](docs/architecture.md)
- [MVP Roadmap](docs/mvp-roadmap.md)
- [New App Guide](docs/new-app-guide.md)
- [Native Adapters](docs/native-adapters.md) — platform-specific input in Swift/C/.NET
- [Consumer SDK Spec](docs/consumer-spec.md) — interface for language SDKs
- [Windows Integration](docs/windows-integration.md)
- [Linux Integration](docs/linux-integration.md)
- [Development TODO](TODO.md)
