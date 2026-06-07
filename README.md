# app-automate

Control desktop applications programmatically. Works on Linux, Windows, and macOS.

## How it works

You create a JSON profile that describes an app's UI elements — buttons, fields, keyboard shortcuts. `app-automate` uses that profile to find targets and perform actions like clicking, typing, or pressing keys.

**One profile format, multiple strategies.** Each element in a profile uses whichever strategy works best for that element:

| Strategy | How it finds the target | Needs display? | Cross-platform? |
|----------|------------------------|----------------|-----------------|
| **Keyboard shortcut** | Sends key combination (e.g. `ctrl+t`) | App must be focused | Yes |
| **Accessibility** (AT-SPI / UIA / AX) | Queries the accessibility tree by role, name, or ID | Yes | Per-platform |
| **CDP** | Targets DOM elements by CSS selector | Yes | WebView2 only |
| **Computer vision** | Matches anchor screenshots at relative coordinates | Yes + screenshots | Yes |

Use whatever combination works for the app. A single profile can mix all of them.

## Install

```bash
uv sync

# Linux: install AT-SPI bindings for accessibility support
sudo apt install python3-gi gir1.2-atspi-2.0 xdotool wmctrl
```

## Quick example

Create a profile (`profile.json`):

```json
{
  "profile_id": "firefox",
  "app_name": "Firefox",
  "type": "semantic",
  "backend": "mixed",
  "shortcuts": {
    "new_tab": {"keys": "ctrl+t", "keys_macos": "cmd+t", "description": "Open new tab"},
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

This profile uses keyboard shortcuts for navigation and accessibility (`role: "entry"`) for the search box. Both strategies in one profile.

Then use it:

```bash
# See what the profile contains
uv run app-automate list-elements my-profile/profile.json

# Preview without acting
uv run app-automate dry-run "url_bar" --profile my-profile/profile.json

# Actually execute
uv run app-automate click "url_bar" --profile my-profile/profile.json
```

## Strategies in detail

### Keyboard shortcuts

When an element has a known keyboard shortcut, you define it with `action: "shortcut"` and a key combination. The SDK sends those keys at runtime.

Key notation uses `+` to combine: `"ctrl+t"`, `"ctrl+shift+s"`, `"f5"`, `"alt+left"`. Per-platform keys are supported: `"keys": "ctrl+s", "keys_macos": "cmd+s"`.

Shortcuts can come from:
- The profile JSON directly (as shown above)
- A standalone JSON file: `{"save": {"keys": "ctrl+s"}, "quit": {"keys": "ctrl+q"}}`
- A plain text file: `save = ctrl+s`
- Live extraction from the app (see `extract-shortcuts` below)

To import shortcuts into a profile from a file:

```bash
uv run app-automate extract-shortcuts Firefox --source file \
  --shortcuts-file my-shortcuts.json
```

To extract from a running app:

```bash
# From AT-SPI menu accelerators (Linux)
uv run app-automate extract-shortcuts Firefox --source atspi-menu

# From GNOME window manager bindings (Linux)
uv run app-automate extract-shortcuts "" --source gnome-wm

# From .desktop files (Linux)
uv run app-automate extract-shortcuts firefox --source desktop
```

### Accessibility — semantic element targeting

Query the app's accessibility tree to find buttons, fields, and menus by role, name, or automation ID.

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

# Extract shortcuts from live app menus and macOS defaults
uv run app-automate extract-shortcuts Safari --source ax-menu
uv run app-automate extract-shortcuts Safari --source plist
uv run app-automate extract-shortcuts "" --source system-hotkeys
```

**Build a semantic profile from the live app:**
```bash
uv run app-automate train --backend atspi --app "Calculator" --output-dir my-profile
uv run app-automate click "5" --profile my-profile/profile.json
```

### Live element search

Query the live accessibility tree without building a profile. Search by label, role, or synonym — then click or type in one step. Works with AX (macOS), UIA (Windows), and AT-SPI (Linux).

```bash
# Find and list elements matching "share"
uv run app-automate search "share" --app Safari

# Filter by element role
uv run app-automate search "search" --app Safari --role textfield

# Find and click the top result (dry-run by default)
uv run app-automate search "share" --app Safari --click --dry-run
uv run app-automate search "share" --app Safari --click --execute

# Find a text field and type into it
uv run app-automate search "email" --app Safari --type "hello@example.com" --execute

# Synonym expansion: "btn" finds buttons, "erase" finds delete, etc.
uv run app-automate search "btn" --app Safari --all
uv run app-automate search "erase" --app TextEdit --all

# JSON output
uv run app-automate search "reload" --app Safari --json
```

### CDP — WebView2 apps (Windows)

```bash
uv run app-automate cdp-setup --app "Outlook"
uv run app-automate cdp-list --actionable-only
uv run app-automate cdp-click --contains "New email" --execute
```

### Visual profiles — computer vision

For apps with poor accessibility support. Takes a screenshot, generates a grid overlay, uses an LLM to build a profile, then matches anchor images at runtime.

```bash
# Requires an OpenAI key in settings
uv run app-automate train --app "MyApp" --output-dir my-profile
uv run app-automate click "save_button" --profile my-profile/profile.json
```

## Profile structure

A profile is a single `profile.json` file. **One schema covers all strategies** — shortcuts, accessibility, and visual elements coexist in the same file.

See the **[Profile Schema Reference](docs/schema-reference.md)** for the complete field-by-field documentation.

`backend` tells the runtime which strategy to prefer: `"shortcut"`, `"atspi"`, `"uia"`, `"ax"`, `"cdp"`, or `"mixed"`. Per-element, the `action` field determines what actually happens.

**Actions available:** `click`, `double_click`, `right_click`, `type`, `drag`, `scroll`, `hotkey`, `wait`, `shortcut`.

## Discovering what's available

```bash
# Auto-detect best backend for an app
uv run app-automate probe "Calculator"

# See what elements are near your cursor
uv run app-automate whats-here --radius 150
```

## Adding a new app

1. **Probe the app** to see what backends are available:
   ```bash
   uv run app-automate probe "AppName"
   ```

2. **Check for shortcuts.** If the app has documented keyboard shortcuts, add them as shortcut elements. You can import from a file or extract live.

3. **Try accessibility.** If the app exposes a good accessibility tree, build a semantic profile:
   ```bash
   uv run app-automate train --backend atspi --app "AppName" --output-dir my-profile
   ```

4. **Fall back to CV** if accessibility is poor:
   ```bash
   uv run app-automate train --app "AppName" --output-dir my-profile
   ```

5. **Combine strategies.** A single profile can contain shortcut elements, accessibility elements, and visual elements. Use whichever works best for each action.

## Example profiles

**Hand-crafted** (`examples/profiles/`):

| Profile | Strategies used | Notes |
|---------|----------------|-------|
| Firefox | Shortcuts + AT-SPI | Shortcuts for navigation, AT-SPI for UI elements |
| Chrome | Shortcuts | 34 shortcuts with per-platform keys |
| VS Code | Shortcuts | 38 shortcuts with per-platform keys |
| LibreOffice Writer | Shortcuts | 40 shortcuts with per-platform keys |
| Galculator | Shortcuts | Linux calculator |

**Auto-imported from ShortcutMapper** (`examples/profiles-imported/`): 20 apps including Blender, Photoshop, IntelliJ IDEA, and more. These are shortcut-only profiles generated from the ShortcutMapper dataset. Run `app-automate validate examples/profiles-imported/<app>` to inspect any of them.

## Using profiles from your own code

The consumer SDK lets you load and execute profiles without the CLI. Available for Python and .NET:

```python
from app_automate.consumer import Consumer

c = Consumer.from_file("profiles/firefox")
c.execute("new tab")          # sends ctrl+t
c.execute("url bar")          # sends ctrl+l
c.type_text("https://example.com")
c.send_key("enter")
```

See [Consumer SDK Spec](docs/consumer-spec.md) and [Native Adapters](docs/native-adapters.md) for .NET, Swift, and C implementations.

## Platform support

| Feature | Linux | Windows | macOS |
|---------|-------|---------|-------|
| Keyboard shortcuts | Yes | Yes | Yes |
| Visual profiles (CV) | Yes | Yes | Yes |
| Accessibility | AT-SPI | UIA | AX (native axtool) |
| Live search | AT-SPI | UIA | AX |
| Browser/WebView | — | CDP | — |
| Window capture | xdotool + mss | user32 + mss | axtool + mss |

## CLI Reference

### Discovery
| Command | Description |
|---------|-------------|
| `probe <app>` | Detect best backend for an app |
| `whats-here` | List elements near cursor |
| `search <query> --app <name>` | Search live accessibility tree by label/role/synonym |
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
| `validate <profile>` | Check profile for issues |
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
- [Consumer SDK Spec](docs/consumer-spec.md) — interface for language SDKs
- [Native Adapters](docs/native-adapters.md) — platform-specific input in Swift/C/.NET
- [New App Guide](docs/new-app-guide.md)
- [Windows Integration](docs/windows-integration.md)
- [Linux Integration](docs/linux-integration.md)
- [Architecture](docs/architecture.md)
- [Development TODO](TODO.md)
