# Profile Schema Reference

One schema. One `profile.json` file. Mix shortcuts, accessibility elements, and visual elements as needed.

## Quick Reference

```json
{
  "profile_id": "my-app",
  "app_name": "MyApp",
  "type": "semantic",
  "backend": "mixed",
  "platform_hint": null,
  "notes": "Optional description",
  "shortcuts": { "...": "see below" },
  "semantic_elements": { "...": "see below" },
  "elements": { "...": "visual profiles only" },
  "states": { "...": "multi-state profiles" },
  "baseline": { "width": 1920, "height": 1080 },
  "anchors": { "...": "visual profiles only" }
}
```

## Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `profile_id` | string | Yes | Unique identifier. Lowercase, hyphens OK. |
| `app_name` | string | Yes | Application name used to find the running process/window. |
| `type` | string | Yes | `"semantic"` (accessibility/shortcuts) or `"visual"` (CV/anchors). |
| `backend` | string or null | Yes for semantic | Primary backend: `"shortcut"`, `"uia"`, `"atspi"`, `"ax"`, `"cdp"`, or `"mixed"`. |
| `platform_hint` | string or null | No | `"windows"`, `"linux"`, `"macos"`, or null for cross-platform. |
| `notes` | string | No | Human-readable notes. |
| `shortcuts` | object | No | Named keyboard shortcuts (see below). |
| `semantic_elements` | object | No | Named semantic elements with actions (see below). |
| `elements` | object | No | Named visual elements with relative coordinates. Used when `type` is `"visual"`. |
| `states` | object | No | Named application states, each with their own anchors and elements. |
| `default_state` | string | No | State ID to use when none specified. Default: `"default"`. |
| `baseline` | object | No | Reference screen resolution `{ "width": 1920, "height": 1080 }` for visual profiles. |
| `anchors` | object | No | Visual anchor images for coordinate transformation in visual profiles. |

---

## `shortcuts` — Keyboard Shortcuts

A dictionary of named shortcuts. Each entry defines a key combination and optional per-platform overrides.

```json
{
  "shortcuts": {
    "save": {
      "keys": "ctrl+s",
      "keys_macos": "cmd+s",
      "description": "Save document"
    },
    "close_tab": {
      "keys": "ctrl+w",
      "keys_macos": "cmd+w",
      "description": "Close current tab"
    },
    "fullscreen": {
      "keys": "f11",
      "description": "Toggle fullscreen"
    }
  }
}
```

### ShortcutDefinition

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `keys` | string | Yes | Default key combination. Used when no platform override matches. |
| `keys_macos` | string or null | No | macOS-specific keys (e.g. `"cmd+t"`). |
| `keys_linux` | string or null | No | Linux-specific keys. |
| `keys_windows` | string or null | No | Windows-specific keys. |
| `description` | string | No | What this shortcut does. |

### Key notation

Use `+` to combine keys. Examples:

| Notation | Meaning |
|----------|---------|
| `"ctrl+t"` | Hold Ctrl, press T |
| `"ctrl+shift+s"` | Hold Ctrl+Shift, press S |
| `"f5"` | Press F5 (no modifiers) |
| `"alt+left"` | Hold Alt, press Left Arrow |

**Modifier names:** `ctrl`, `cmd`, `alt`, `shift`

**Special keys:** `enter`, `tab`, `escape`, `backspace`, `delete`, `space`, `up`, `down`, `left`, `right`, `pageup`, `pagedown`, `home`, `end`, `capslock`, `f1` through `f12`

**Platform resolution:** At runtime, the SDK calls `keys_for_platform()` which returns `keys_macos` on macOS, `keys_linux` on Linux, `keys_windows` on Windows, or falls back to `keys`. You only need platform overrides when they differ from the default.

---

## `semantic_elements` — Actionable Elements

A dictionary of named elements. Each element has a label, optional aliases for natural language lookup, and an action.

### SemanticElement

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `label` | string | Yes | Display name for this element. |
| `aliases` | string[] | No | Alternative names for lookup. Matched case-insensitive. |
| `action` | string | Yes | What to do: `"shortcut"`, `"click"`, `"double_click"`, `"right_click"`, `"type"`, `"drag"`, `"scroll"`, `"hotkey"`, `"wait"`. |
| `shortcut` | ShortcutDefinition | No | Required when action is `"shortcut"`. |
| `role` | string or null | No | Accessibility role for finding the element (e.g. `"button"`, `"entry"`). |
| `automation_id` | string or null | No | UIA AutomationId (Windows). |
| `selector` | string or null | No | CSS selector (CDP/web). |
| `hotkey` | string or null | No | Key combination for `"hotkey"` action. |
| `text` | string or null | No | Text to type for `"type"` action. |
| `drag_dx` | number or null | No | Horizontal drag distance for `"drag"` action. |
| `drag_dy` | number or null | No | Vertical drag distance for `"drag"` action. |
| `scroll_clicks` | integer or null | No | Scroll amount for `"scroll"` action. |
| `wait_ms` | integer or null | No | Wait time in ms for `"wait"` action. |

### Actions

| Action | What happens | Required fields |
|--------|-------------|-----------------|
| `shortcut` | Send keyboard shortcut | `shortcut: {keys: "ctrl+t"}` |
| `hotkey` | Send key combination | `hotkey: "ctrl+shift+i"` |
| `click` | Click the element | `role` or `automation_id` or `selector` |
| `double_click` | Double-click | Same as click |
| `right_click` | Right-click | Same as click |
| `type` | Click element, then type text | `role`/`selector` + `text` or runtime text |
| `drag` | Click and drag | `drag_dx`, `drag_dy` |
| `scroll` | Scroll at element | `scroll_clicks` |
| `wait` | Pause execution | `wait_ms` (default 500) |

### Examples

**Shortcut element (cross-platform):**
```json
"new_tab": {
  "label": "new_tab",
  "aliases": ["open tab", "new tab"],
  "action": "shortcut",
  "shortcut": {
    "keys": "ctrl+t",
    "keys_macos": "cmd+t",
    "description": "Open new tab"
  }
}
```

**Accessibility click element (Linux AT-SPI):**
```json
"button_5": {
  "label": "5",
  "aliases": ["five"],
  "role": "push button",
  "action": "click"
}
```

**Accessibility type element (Windows UIA):**
```json
"search_box": {
  "label": "Search",
  "aliases": ["find", "search box"],
  "automation_id": "SearchTextBox",
  "action": "type",
  "text": ""
}
```

**Wait element:**
```json
"page_load": {
  "label": "wait for page load",
  "action": "wait",
  "wait_ms": 2000
}
```

---

## `elements` — Visual Elements

For `type: "visual"` profiles. Each element has a position relative to anchor points.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `label` | string | Yes | Display name. |
| `aliases` | string[] | No | Alternative names. |
| `rel_x` | number | Yes | X position relative to anchor (0-1). |
| `rel_y` | number | Yes | Y position relative to anchor (0-1). |
| `layout` | string | Yes | How to resolve: `"fixed_from_primary"`, `"top_right"`, `"bottom_right"`, `"center_scaled"`. |
| `action` | string | No | Same actions as semantic elements. Default: `"click"`. |

---

## `states` — Multi-State Profiles

For apps that change layout (e.g. editor vs preview mode). Each state has its own anchors and elements.

```json
{
  "states": {
    "edit": {
      "id": "edit",
      "anchors": { "primary": { "id": "toolbar", "path": "anchors/toolbar.png", "x": 960, "y": 40 } },
      "elements": { "save_btn": { "label": "Save", "rel_x": 0.5, "rel_y": 0.03, "layout": "fixed_from_primary" } }
    },
    "preview": {
      "id": "preview",
      "signature": { "check_regions": [ { "path": "anchors/preview_indicator.png", "x": 100, "y": 10 } ] },
      "anchors": { "primary": { "id": "preview_bar", "path": "anchors/preview_bar.png", "x": 960, "y": 50 } },
      "elements": { "close_preview": { "label": "Close", "rel_x": 0.95, "rel_y": 0.03, "layout": "fixed_from_primary" } }
    }
  }
}
```

---

## How Sections Relate

```
profile.json
│
├── shortcuts {}              ← Standalone shortcut lookup table
│                                "save" → "ctrl+s"
│
├── semantic_elements {}      ← Named elements with actions
│   ├── "save" → action: "shortcut", shortcut: {keys: "ctrl+s"}
│   ├── "search_box" → action: "type", role: "entry"
│   └── "zoom_in" → action: "shortcut", shortcut: {keys: "ctrl+plus"}
│
├── elements {}               ← Visual/CV elements (type: "visual")
│   └── "save_btn" → rel_x: 0.5, rel_y: 0.03, layout: "fixed_from_primary"
│
└── states {}                 ← Named states with own anchors+elements
    ├── "edit" → { anchors, elements }
    └── "preview" → { anchors, elements }
```

`shortcuts` and `semantic_elements` can reference the same shortcut keys — `shortcuts` is a flat lookup, `semantic_elements` adds aliases and action context. Most consumers use `semantic_elements` for resolution.

---

## Validation

Validate any profile:

```bash
app-automate validate examples/profiles/firefox
```

Checks for: missing backend, empty shortcut keys, duplicate aliases, shortcut actions without shortcut definitions, and more.

---

## JSON Schema

Machine-readable: [`docs/schemas/profile.json`](schemas/profile.json) (JSON Schema draft 2020-12).

Use it for validation in editors, CI, or SDKs:

```bash
pip install jsonschema
python -m jsonschema docs/schemas/profile.json -i examples/profiles/firefox/profile.json
```
