# Consumer SDK Specification

This document defines the minimal interface that any app-automate consumer SDK must implement. Language-specific SDKs (.NET, Python, JS, etc.) should follow this spec so that profile consumers are interchangeable.

## Profile Format

Profiles are JSON files described by `docs/schemas/profile.json` (JSON Schema draft 2020-12). Every SDK must be able to load and validate a profile against this schema.

## Core Operations

### 1. Load Profile

```text
Profile load(string path)
```

Load and validate a profile from a file path or directory (directory should auto-resolve to `profile.json` inside it).

### 2. Resolve Element

```text
Element? resolve(Profile profile, string command)
```

Given a natural language command (e.g. "new tab", "url bar", "bold"), find the matching semantic element. Matching is case-insensitive against:
- The element's `label`
- Each alias in `aliases`
- The element's dictionary key

If no match is found, return null/throw.

### 3. List Available Commands

```text
string[] list_commands(Profile profile)
```

Return all resolvable command names (labels + aliases) for discoverability and autocomplete.

### 4. Execute Action

```text
Result execute(Profile profile, string command, object? options)
```

Execute the action for a matched element. The `options` parameter is optional and may include:

| Field    | Type     | Description                                    |
|----------|----------|------------------------------------------------|
| `text`   | `string` | Text to type (for `type` actions)              |
| `dryRun` | `bool`   | If true, resolve but don't execute (default: false) |

Returns a `Result` with:

| Field       | Type     | Description                          |
|-------------|----------|--------------------------------------|
| `elementId` | `string` | The matched element's dictionary key |
| `label`     | `string` | Element label                        |
| `action`    | `string` | Action performed                     |
| `x`         | `float?` | X coordinate (if applicable)         |
| `y`         | `float?` | Y coordinate (if applicable)         |

### 5. Send Shortcut

```text
void send_shortcut(string keys)
```

Send a keyboard shortcut using the platform's native input API. The `keys` string uses `+` notation: `"ctrl+t"`, `"alt+left"`, `"f5"`, `"ctrl+shift+n"`.

On macOS, SDKs should automatically map `ctrl` → `cmd` for standard shortcuts unless the profile specifies `platform: "macos"` explicitly.

## Action Types

Each resolved element has an `action` that determines what the SDK must do:

| Action         | What the SDK does                                              |
|----------------|----------------------------------------------------------------|
| `shortcut`     | Parse `element.shortcut.keys` and call `send_shortcut()`       |
| `click`        | Click at the element's coordinates                             |
| `type`         | Click the element, then type `text` from options or profile    |
| `double_click` | Double-click at coordinates                                    |
| `right_click`  | Right-click at coordinates                                     |
| `drag`         | Click at element, drag by `drag_dx`, `drag_dy`                 |
| `scroll`       | Scroll at element by `scroll_clicks`                           |
| `hotkey`       | Send `element.hotkey` key combination                          |
| `wait`         | Sleep for `element.wait_ms` milliseconds                       |

**For shortcut-only profiles** (backend = "shortcut"), only `shortcut`, `hotkey`, `type`, and `wait` actions are relevant. No screen coordinates or accessibility tree is needed.

## Platform Input

Each SDK is responsible for implementing platform-native input:

| Platform | Send Keys                        | Click / Mouse                     |
|----------|----------------------------------|-----------------------------------|
| Windows  | `SendInput` / `InputSimulator`   | `SendInput` with mouse events     |
| macOS    | `CGEvent` / AppleScript          | `CGEvent` mouse events            |
| Linux    | `xdotool` / `ydotool` (Wayland) | `xdotool` / `ydotool`             |

SDKs should **not** depend on the app-automate Python package. They are standalone libraries that only need the profile JSON.

## Error Handling

- **Element not found**: Throw/return error with message including the command attempted and available commands.
- **Profile validation error**: Throw/return error with details of which fields failed validation.
- **Platform not supported**: Throw if a coordinate-based action is attempted but no accessibility backend is available.

## Example Usage (.NET)

```csharp
var profile = Profile.Load("examples/profiles/firefox/profile.json");

// List available commands
foreach (var cmd in profile.ListCommands())
    Console.WriteLine(cmd);
// Output: new tab, open tab, close tab, url bar, address bar, ...

// Execute a shortcut
var result = profile.Execute("new tab");
// Sends Ctrl+T (or Cmd+T on macOS)

// Type into the URL bar
profile.Execute("url bar");   // focuses via Ctrl+L
profile.SendShortcut("ctrl+a");
profile.TypeText("https://example.com");
profile.SendShortcut("enter");
```

## Example Usage (Python)

```python
from app_automate.consumer import Consumer

c = Consumer.from_file("examples/profiles/firefox/profile.json")

# List commands
print(c.list_commands())

# Execute
c.execute("new tab")          # sends ctrl+t
c.execute("url bar")          # sends ctrl+l
c.type_text("https://example.com")
c.send_key("enter")
```

## Profile Discovery

SDKs may optionally support discovering profiles in well-known locations:
- `./profiles/` (current directory)
- `~/.config/app-automate/profiles/` (user config)
- Bundled profiles shipped with the SDK

This is optional and not required for minimum compliance.
