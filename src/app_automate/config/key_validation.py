from __future__ import annotations

KNOWN_MODIFIERS = frozenset(
    {
        "ctrl",
        "control",
        "cmd",
        "command",
        "alt",
        "option",
        "shift",
        "super",
        "meta",
        "win",
    }
)

KNOWN_SPECIAL_KEYS = frozenset(
    {
        "enter",
        "return",
        "tab",
        "escape",
        "esc",
        "backspace",
        "delete",
        "del",
        "space",
        "spacebar",
        "insert",
        "ins",
        "home",
        "end",
        "pageup",
        "pgup",
        "pagedown",
        "pgdn",
        "capslock",
        "up",
        "down",
        "left",
        "right",
        "f1",
        "f2",
        "f3",
        "f4",
        "f5",
        "f6",
        "f7",
        "f8",
        "f9",
        "f10",
        "f11",
        "f12",
        "numlock",
        "scrolllock",
        "printscreen",
        "prtsc",
        "pause",
        "menu",
        "apps",
        "plus",
        "minus",
        "equals",
        "numpad_0",
        "numpad_1",
        "numpad_2",
        "numpad_3",
        "numpad_4",
        "numpad_5",
        "numpad_6",
        "numpad_7",
        "numpad_8",
        "numpad_9",
        "numpad_enter",
        "numpad_plus",
        "numpad_minus",
        "numpad_multiply",
        "numpad_divide",
        "numpad_decimal",
    }
)

PLATFORM_SPECIFIC: dict[str, frozenset[str]] = {
    "macos": frozenset({"cmd", "command"}),
    "windows": frozenset({"win", "apps"}),
    "linux": frozenset({"super", "meta"}),
}


def validate_key_string(keys: str, *, platform: str | None = None) -> list[str]:
    if not keys or not keys.strip():
        return ["empty key string"]

    stripped = keys.strip()
    if stripped == "+":
        return []

    parts = [p.strip() for p in stripped.split("+")]
    parts = [p for p in parts if p]
    if not parts:
        return ["empty key string"]

    warnings: list[str] = []
    allowed_platform = (
        PLATFORM_SPECIFIC.get(platform, frozenset()) if platform else frozenset()
    )

    for part in parts:
        lower = part.lower()
        if lower in KNOWN_MODIFIERS or lower in KNOWN_SPECIAL_KEYS:
            continue
        if lower in allowed_platform:
            continue
        if len(part) == 1:
            continue
        if lower.startswith("f") and len(lower) <= 3:
            try:
                n = int(lower[1:])
                if 1 <= n <= 24:
                    continue
            except ValueError:
                pass
        warnings.append(f"unknown key: '{part}'")

    return warnings
