# Native Adapters

The consumer SDK loads profiles (pure JSON) and resolves elements. But sending actual keystrokes and clicks requires platform-native input APIs. This document shows how to write a native adapter for each platform.

## The Interface

Every adapter implements three methods:

| Method | What it does |
|--------|-------------|
| `SendShortcut(string keys)` | Send a key combination like `"ctrl+t"` or `"cmd+shift+s"` |
| `TypeText(string text)` | Type a string character by character |
| `SendKey(string key)` | Press a single key like `"enter"` or `"tab"` |

That's it. The SDK handles profile loading, element resolution, and key string parsing. You just implement the input.

## Key Format

Keys use `+` notation. Parse by splitting on `+`:

| Input | Meaning |
|-------|---------|
| `"ctrl+t"` | Hold Ctrl, press T |
| `"cmd+shift+s"` | Hold Cmd+Shift, press S |
| `"f5"` | Press F5 (no modifiers) |
| `"alt+left"` | Hold Alt, press Left Arrow |
| `"enter"` | Press Enter |

Modifier names: `ctrl`, `cmd`, `alt`, `shift`, `option` (= alt)

Special keys: `enter`, `tab`, `escape`, `backspace`, `delete`, `space`, `up`, `down`, `left`, `right`, `pageup`, `pagedown`, `home`, `end`, `capslock`, `f1`–`f12`

---

## Windows — .NET (SendInput)

This is the most complete example. Uses P/Invoke to call `SendInput` directly — no third-party packages needed.

```csharp
using System.Runtime.InteropServices;
using AppAutomate.Consumer;

public sealed class WindowsNativeAdapter : IInputAdapter
{
    [DllImport("user32.dll", SetLastError = true)]
    static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);

    [StructLayout(LayoutKind.Sequential)]
    struct INPUT
    {
        public uint type; // 1 = KEYBOARD
        public INPUTUNION u;
    }

    [StructLayout(LayoutKind.Explicit)]
    struct INPUTUNION
    {
        [FieldOffset(0)] public KEYBDINPUT ki;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct KEYBDINPUT
    {
        public ushort wVk;
        public ushort wScan;
        public uint dwFlags; // 0 = keydown, 2 = keyup
        public uint time;
        public IntPtr dwExtraInfo;
    }

    public void SendShortcut(string keys)
    {
        var parts = keys.Split('+');
        var vks = parts.Select(ParseVk).ToArray();
        var modifiers = vks[..^1];
        var mainKey = vks[^1];

        // Press modifiers
        foreach (var vk in modifiers)
            SendKeyInput(vk, keyDown: true);

        // Press and release main key
        SendKeyInput(mainKey, keyDown: true);
        SendKeyInput(mainKey, keyDown: false);

        // Release modifiers (reverse order)
        foreach (var vk in modifiers.Reverse())
            SendKeyInput(vk, keyDown: false);
    }

    public void TypeText(string text)
    {
        foreach (char c in text)
        {
            SendKeyInput(VkKeyScan(c), keyDown: true);
            SendKeyInput(VkKeyScan(c), keyDown: false);
        }
    }

    public void SendKey(string key) => SendShortcut(key);

    void SendKeyInput(ushort vk, bool keyDown)
    {
        var input = new INPUT
        {
            type = 1,
            u = new INPUTUNION
            {
                ki = new KEYBDINPUT
                {
                    wVk = vk,
                    dwFlags = keyDown ? (uint)0 : (uint)2
                }
            }
        };
        SendInput(1, [input], Marshal.SizeOf<INPUT>());
    }

    [DllImport("user32.dll")]
    static extern ushort VkKeyScan(char ch);

    static ushort ParseVk(string key) => key.ToLower() switch
    {
        "ctrl" => 0x11,
        "alt" or "option" => 0x12,
        "shift" => 0x10,
        "enter" => 0x0D,
        "tab" => 0x09,
        "escape" => 0x1B,
        "backspace" => 0x08,
        "delete" => 0x2E,
        "space" => 0x20,
        "left" => 0x25,
        "up" => 0x26,
        "right" => 0x27,
        "down" => 0x28,
        "pageup" => 0x21,
        "pagedown" => 0x22,
        "home" => 0x24,
        "end" => 0x23,
        var f when f.StartsWith("f") && int.TryParse(f[1..], out var n) && n is >= 1 and <= 12
            => (ushort)(0x70 + n - 1),
        var c when c.Length == 1 => (ushort)char.ToUpper(c[0]),
        _ => 0
    };
}
```

**Usage:**

```csharp
var adapter = new WindowsNativeAdapter();
var consumer = Consumer.FromFile("profiles/firefox", adapter);

consumer.Execute("new tab");   // Sends Ctrl+T via SendInput
consumer.Execute("url bar");   // Sends Ctrl+L
adapter.TypeText("https://example.com");
adapter.SendKey("enter");
```

**Why native instead of pyautogui?** `SendInput` is the official Windows API. It works with UAC-elevated apps if your binary has `uiAccess=true` in its manifest (requires code signing). Python can't get UIAccess.

---

## macOS — Swift (CGEvent)

macOS requires the **Accessibility permission** (System Settings → Privacy & Security → Accessibility). The binary must be signed and have a stable path — this is the main reason to go native on macOS.

```swift
import Cocoa

class NativeAdapter {
    // Send a keyboard shortcut like "cmd+t" or "ctrl+shift+s"
    func sendShortcut(_ keys: String) {
        let parts = keys.split(separator: "+").map(String.init)
        let modifiers = parts.dropLast().map(parseModifier)
        let mainKey = parts.last!

        let source = CGEventSource(stateID: .hidSystemState)

        // Build modifier flags
        var flags: CGEventFlags = []
        for mod in modifiers {
            flags.insert(mod)
        }

        // Key down
        if let keyDown = CGEvent(keyboardEventSource: source,
                                  virtualKey: parseKey(mainKey),
                                  keyDown: true) {
            keyDown.flags = flags
            keyDown.post(tap: .cghidEventTap)
        }

        // Key up
        if let keyUp = CGEvent(keyboardEventSource: source,
                                virtualKey: parseKey(mainKey),
                                keyDown: false) {
            keyUp.flags = flags
            keyUp.post(tap: .cghidEventTap)
        }
    }

    func typeText(_ text: String) {
        let source = CGEventSource(stateID: .hidSystemState)
        for char in text {
            let uni = char.utf16.first!
            if let keyDown = CGEvent(keyboardEventSource: source,
                                      virtualKey: 0,
                                      keyDown: true) {
                keyDown.keyboardSetUnicodeString(maxStringLength: 1,
                                                  unicodeString: &([uni]))
                keyDown.post(tap: .cghidEventTap)
            }
            if let keyUp = CGEvent(keyboardEventSource: source,
                                    virtualKey: 0,
                                    keyDown: false) {
                keyUp.keyboardSetUnicodeString(maxStringLength: 1,
                                                unicodeString: &([uni]))
                keyUp.post(tap: .cghidEventTap)
            }
        }
    }

    func sendKey(_ key: String) {
        sendShortcut(key)
    }

    private func parseModifier(_ mod: String) -> CGEventFlags {
        switch mod.lowercased() {
        case "cmd", "command": return .maskCommand
        case "ctrl", "control": return .maskControl
        case "alt", "option": return .maskAlternate
        case "shift": return .maskShift
        default: return []
        }
    }

    private func parseKey(_ key: String) -> CGKeyCode {
        switch key.lowercased() {
        case "enter", "return": return 0x24
        case "tab": return 0x30
        case "escape": return 0x35
        case "backspace", "delete": return 0x33
        case "space": return 0x31
        case "left": return 0x7B
        case "right": return 0x7C
        case "down": return 0x7D
        case "up": return 0x7E
        case "pageup": return 0x74
        case "pagedown": return 0x79
        case "home": return 0x73
        case "end": return 0x77
        case let f where f.hasPrefix("f"):
            if let n = Int(f.dropFirst()), n >= 1, n <= 12 {
                return CGKeyCode(0x5A + n - 1)
            }
            return 0
        case let c where c.count == 1:
            // Map a-z to virtual keycodes
            let scalars = "abcdefghijklmnopqrstuvwxyz"
            if let idx = scalars.firstIndex(of: Character(c.lowercased())) {
                return CGKeyCode(scalars.distance(from: scalars.startIndex, to: idx) + 0x04)
            }
            return 0
        default: return 0
        }
    }
}
```

**Why native on macOS?** The Accessibility permission is per-binary. A signed Swift framework or app extension gets a stable identity. Python's `uv` venv path changes every rebuild, breaking the permission. Real assistive tech products on macOS are always native for this reason.

---

## Linux — C (XTest / ydotool)

Linux is the simplest — no permission model for input. `xdotool` works on X11, `ydotool` works on both X11 and Wayland. But if you want to avoid shelling out:

```c
#include <X11/Xlib.h>
#include <X11/extensions/XTest.h>
#include <string.h>
#include <ctype.h>

// Send a key combo like "ctrl+t"
void send_shortcut(Display *display, const char *keys) {
    char *copy = strdup(keys);
    char *token = strtok(copy, "+");
    KeyCode keycodes[16];
    int count = 0;

    while (token != NULL && count < 15) {
        keycodes[count++] = parse_keycode(display, token);
        token = strtok(NULL, "+");
    }
    free(copy);

    // Press modifiers
    for (int i = 0; i < count - 1; i++)
        XTestFakeKeyEvent(display, keycodes[i], True, 0);

    // Press and release main key
    XTestFakeKeyEvent(display, keycodes[count-1], True, 0);
    XTestFakeKeyEvent(display, keycodes[count-1], False, 0);

    // Release modifiers
    for (int i = count - 2; i >= 0; i--)
        XTestFakeKeyEvent(display, keycodes[i], False, 0);

    XFlush(display);
}

void type_text(Display *display, const char *text) {
    for (int i = 0; text[i]; i++) {
        KeySym ks = XStringToKeysym((char[]){text[i], 0});
        KeyCode kc = XKeysymToKeycode(display, ks);
        XTestFakeKeyEvent(display, kc, True, 0);
        XTestFakeKeyEvent(display, kc, False, 0);
    }
    XFlush(display);
}

KeyCode parse_keycode(Display *dpy, const char *name) {
    char lower[32];
    for (int i = 0; name[i] && i < 31; i++)
        lower[i] = tolower(name[i]);
    lower[strlen(name)] = 0;

    if (strcmp(lower, "ctrl") == 0) return XKeysymToKeycode(dpy, XK_Control_L);
    if (strcmp(lower, "alt") == 0) return XKeysymToKeycode(dpy, XK_Alt_L);
    if (strcmp(lower, "shift") == 0) return XKeysymToKeycode(dpy, XK_Shift_L);
    if (strcmp(lower, "enter") == 0) return XKeysymToKeycode(dpy, XK_Return);
    if (strcmp(lower, "tab") == 0) return XKeysymToKeycode(dpy, XK_Tab);
    if (strcmp(lower, "escape") == 0) return XKeysymToKeycode(dpy, XK_Escape);
    if (strcmp(lower, "left") == 0) return XKeysymToKeycode(dpy, XK_Left);
    if (strcmp(lower, "right") == 0) return XKeysymToKeycode(dpy, XK_Right);
    if (strcmp(lower, "up") == 0) return XKeysymToKeycode(dpy, XK_Up);
    if (strcmp(lower, "down") == 0) return XKeysymToKeycode(dpy, XK_Down);

    return XKeysymToKeycode(dpy, XStringToKeysym(lower));
}

// Compile: gcc -lX11 -lXtst adapter.c -o adapter
```

**For Wayland**, replace XTest with `ydotool` (uses `/dev/uinput`) or libei. The shortcut parsing stays the same.

---

## Integrating with the Profile

Regardless of language, the pattern is:

```
1. Load profile.json (any JSON library)
2. Resolve element by command name
3. Get keys from element.shortcut
4. Resolve platform: keys_macos on macOS, keys on everything else
5. Parse "ctrl+t" into modifiers + key
6. Send via native API
```

The profile JSON schema is stable and documented in `docs/schemas/profile.json`. You don't need the Python package to use profiles — just parse the JSON.

---

## Publishing Roadmap

| Platform | Package | Status |
|----------|---------|--------|
| .NET (NuGet) | `AppAutomate.Consumer` | Skeleton in `sdks/dotnet/` — needs native `SendInput` adapter + NuGet publish |
| Swift (SPM) | Not started | Needs `Package.swift` + CGEvent adapter |
| C/C++ (header-only) | Not started | Needs `adapter.h` with XTest/ydotool implementations |

Each package should contain:
- Profile model classes (JSON deserialization)
- Element resolver (case-insensitive label/alias matching)
- Platform-aware key resolution (`keys_macos` etc.)
- Native input adapter for that platform
