from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app_automate.config.models import ShortcutDefinition

_BUNDLE_ID_MAP: dict[str, str] = {
    "safari": "com.apple.Safari",
    "textedit": "com.apple.TextEdit",
    "notes": "com.apple.Notes",
    "finder": "com.apple.finder",
    "mail": "com.apple.Mail",
    "calendar": "com.apple.iCal",
    "contacts": "com.apple.AddressBook",
    "terminal": "com.apple.Terminal",
    "itunes": "com.apple.iTunes",
    "music": "com.apple.Music",
    "photos": "com.apple.Photos",
    "preview": "com.apple.Preview",
    "xcode": "com.apple.dt.Xcode",
    "pages": "com.apple.iWork.Pages",
    "numbers": "com.apple.iWork.Numbers",
    "keynote": "com.apple.iWork.Keynote",
    "google chrome": "com.google.Chrome",
    "firefox": "org.mozilla.firefox",
    "vscode": "com.microsoft.VSCode",
    "code": "com.microsoft.VSCode",
    "slack": "com.tinyspeck.slackmacgap",
    "discord": "com.hnc.Discord",
    "spotify": "com.spotify.client",
    "iterm": "com.googlecode.iterm2",
    "iterm2": "com.googlecode.iterm2",
}


@dataclass(slots=True)
class ExtractedShortcut:
    action: str
    keys: str
    source: str
    description: str = ""
    platform: str | None = None

    def to_definition(self) -> ShortcutDefinition:
        return ShortcutDefinition(
            keys=self.keys,
            description=self.description,
            platform=self.platform,
        )


def extract_from_desktop_file(app_name: str) -> list[ExtractedShortcut]:
    shortcuts: list[ExtractedShortcut] = []
    candidates = [
        Path("/usr/share/applications"),
        Path.home() / ".local/share/applications",
    ]
    for desktop_dir in candidates:
        if not desktop_dir.is_dir():
            continue
        for desktop_file in desktop_dir.glob("*.desktop"):
            if app_name.lower() not in desktop_file.name.lower():
                continue
            content = desktop_file.read_text(errors="replace")
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("Name="):
                    shortcuts.append(
                        ExtractedShortcut(
                            action=f"launch_{app_name.lower()}",
                            keys="",
                            source=f"desktop:{desktop_file.name}",
                            description=f"Launch {line.split('=', 1)[1].strip()}",
                        )
                    )
    return shortcuts


def extract_from_gnome_wm() -> list[ExtractedShortcut]:
    shortcuts: list[ExtractedShortcut] = []
    try:
        import subprocess

        result = subprocess.run(
            ["gsettings", "list-recursively", "org.gnome.desktop.wm.keybindings"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return shortcuts
        for line in result.stdout.strip().splitlines():
            parts = line.strip().split(None, 2)
            if len(parts) < 3:
                continue
            _, action, keys_str = parts
            keys_str = keys_str.strip().strip("[]'")
            if not keys_str or keys_str == "@as":
                continue
            keys_raw = keys_str.replace("'", "").split(",")
            keys = _normalise_gnome_keys(keys_raw)
            if keys:
                shortcuts.append(
                    ExtractedShortcut(
                        action=action,
                        keys=keys,
                        source="gnome-wm",
                        description=f"GNOME window manager: {action}",
                        platform="linux",
                    )
                )
    except Exception:
        pass
    return shortcuts


def extract_from_atspi_menus(app_name: str) -> list[ExtractedShortcut]:
    shortcuts: list[ExtractedShortcut] = []
    try:
        from app_automate.accessibility.linux_atspi import _ensure_gi_atspi

        Atspi = _ensure_gi_atspi()

        desktop = Atspi.get_desktop(0)
        for i in range(desktop.get_child_count()):
            app = desktop.get_child_at_index(i)
            if app is None:
                continue
            if app.get_role_name() != "application":
                continue
            name = app.get_name() or ""
            if app_name.lower() not in name.lower():
                continue
            _walk_menu_for_accels(app, shortcuts, depth=0, max_depth=12)
            break
    except Exception:
        pass
    return shortcuts


def extract_from_shortcuts_file(path: Path) -> list[ExtractedShortcut]:
    shortcuts: list[ExtractedShortcut] = []
    if not path.exists():
        return shortcuts
    import json

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        _parse_text_shortcuts(path, shortcuts)
        return shortcuts

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "keys" in item and "action" in item:
                shortcuts.append(
                    ExtractedShortcut(
                        action=item["action"],
                        keys=item["keys"],
                        source=f"file:{path.name}",
                        description=item.get("description", ""),
                        platform=item.get("platform"),
                    )
                )
    elif isinstance(data, dict):
        for action, keys in data.items():
            if isinstance(keys, str):
                shortcuts.append(
                    ExtractedShortcut(
                        action=action,
                        keys=keys,
                        source=f"file:{path.name}",
                    )
                )
            elif isinstance(keys, dict):
                shortcuts.append(
                    ExtractedShortcut(
                        action=action,
                        keys=keys.get("keys", ""),
                        source=f"file:{path.name}",
                        description=keys.get("description", ""),
                        platform=keys.get("platform"),
                    )
                )
    return shortcuts


def extract_from_uia_accelerators(app_name: str) -> list[ExtractedShortcut]:
    shortcuts: list[ExtractedShortcut] = []
    try:
        from app_automate.accessibility import windows_uia

        elements = windows_uia.list_app_ui_elements(
            app_name, max_depth=15, actionable_only=False
        )
        for el in elements:
            if not el.path or "menu" not in (el.role or "").lower():
                continue
            accel = getattr(el, "accelerator_key", None)
            if accel:
                shortcuts.append(
                    ExtractedShortcut(
                        action=el.label,
                        keys=_normalise_windows_accel(accel),
                        source="uia-menu",
                        description=el.label,
                        platform="windows",
                    )
                )
    except Exception:
        pass
    return shortcuts


def extract_from_ax_menu_items(app_name: str) -> list[ExtractedShortcut]:
    shortcuts: list[ExtractedShortcut] = []
    try:
        from app_automate.accessibility import macos_ax

        raw_items = macos_ax.extract_menu_shortcuts(app_name)
        for item in raw_items:
            cmd_char = item.get("cmd_char", "")
            cmd_mods = item.get("cmd_modifiers")
            if not cmd_char:
                continue
            keys = _normalise_macos_shortcut(cmd_char, cmd_mods)
            shortcuts.append(
                ExtractedShortcut(
                    action=str(item.get("action", "")),
                    keys=keys,
                    source="ax-menu",
                    description=str(item.get("description", "")),
                    platform="macos",
                )
            )
    except Exception:
        pass
    return shortcuts


def extract_all(app_name: str) -> list[ExtractedShortcut]:
    from app_automate.platform_utils import is_linux, is_macos, is_windows

    all_shortcuts: list[ExtractedShortcut] = []

    all_shortcuts.extend(extract_from_desktop_file(app_name))

    if is_linux():
        all_shortcuts.extend(extract_from_gnome_wm())
        all_shortcuts.extend(extract_from_atspi_menus(app_name))
    elif is_windows():
        all_shortcuts.extend(extract_from_uia_accelerators(app_name))
    elif is_macos():
        all_shortcuts.extend(extract_from_ax_menu_items(app_name))
        all_shortcuts.extend(extract_from_plist(app_name))
        all_shortcuts.extend(extract_system_shortcuts())

    return all_shortcuts


def extract_from_plist(app_name: str) -> list[ExtractedShortcut]:
    shortcuts: list[ExtractedShortcut] = []
    try:
        import plistlib
        import subprocess

        bundle_id = _resolve_bundle_id(app_name)
        if bundle_id is None:
            return shortcuts

        result = subprocess.run(
            ["defaults", "export", bundle_id, "-"],
            check=False,
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            return shortcuts

        plist = plistlib.loads(result.stdout)
        equivalents = plist.get("NSUserKeyEquivalents", {})
        for menu_title, key_spec in equivalents.items():
            keys = _normalise_plist_shortcut(key_spec)
            if keys:
                shortcuts.append(
                    ExtractedShortcut(
                        action=menu_title,
                        keys=keys,
                        source=f"plist:{bundle_id}",
                        description=menu_title,
                        platform="macos",
                    )
                )
    except Exception:
        pass
    return shortcuts


def extract_system_shortcuts() -> list[ExtractedShortcut]:
    shortcuts: list[ExtractedShortcut] = []
    try:
        import plistlib
        import subprocess

        result = subprocess.run(
            [
                "defaults",
                "export",
                "com.apple.symbolichotkeys",
                "-",
            ],
            check=False,
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            return shortcuts

        plist = plistlib.loads(result.stdout)
        hotkeys = plist.get("AppleSymbolicHotKeys", {})
        for key_id, hotkey_def in hotkeys.items():
            if not isinstance(hotkey_def, dict):
                continue
            if not hotkey_def.get("enabled"):
                continue
            value = hotkey_def.get("value", {})
            params = value.get("parameters", [])
            if len(params) < 3:
                continue
            description = _system_hotkey_name(str(key_id))
            if description is None:
                continue
            keys = _params_to_keys(params)
            if keys:
                shortcuts.append(
                    ExtractedShortcut(
                        action=description,
                        keys=keys,
                        source="system-hotkeys",
                        description=description,
                        platform="macos",
                    )
                )
    except Exception:
        pass
    return shortcuts


def _resolve_bundle_id(app_name: str) -> str | None:
    lower = app_name.lower().strip()
    if lower in _BUNDLE_ID_MAP:
        return _BUNDLE_ID_MAP[lower]

    import subprocess

    result = subprocess.run(
            [
                "mdfind",
                (
                    f"kMDItemKind == 'Application' && "
                    f"kMDItemFSName == '{app_name}.app'"
                ),
            ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None

    app_path = result.stdout.strip().split("\n")[0]
    info_path = f"{app_path}/Contents/Info.plist"
    try:
        import plistlib

        with open(info_path, "rb") as f:
            plist = plistlib.load(f)
        return plist.get("CFBundleIdentifier")
    except Exception:
        return None


def _parse_defaults_dict(raw: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for line in raw.strip().splitlines():
        line = line.strip().rstrip(";")
        if not line or line in ("{", "}"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().strip('"')
        value = value.strip().strip('"')
        result[key] = value
    return result


def _normalise_plist_shortcut(key_spec: str) -> str:
    parts: list[str] = []
    chars = list(key_spec)
    i = 0
    while i < len(chars):
        c = chars[i]
        if c == "@":
            parts.append("cmd")
        elif c == "$":
            parts.append("shift")
        elif c == "^":
            parts.append("ctrl")
        elif c == "~":
            parts.append("alt")
        elif c == "`" and len(parts) == 0:
            pass
        else:
            parts.append(c.lower())
            break
        i += 1
    if not parts:
        return ""
    if all(p in ("cmd", "shift", "ctrl", "alt") for p in parts):
        return ""
    return "+".join(parts)


_SYSTEM_HOTKEY_NAMES: dict[str, str] = {
    "1": "Toggle Spotlight",
    "2": "Toggle Spotlight (search field)",
    "3": "Show Spotlight search",
    "6": "Show Dock",
    "7": "Show Dock (autohide)",
    "10": "Move focus to menu bar",
    "11": "Move focus to Dock",
    "12": "Move focus to active window",
    "13": "Move focus to window toolbar",
    "14": "Move focus to floating window",
    "15": "Move focus to next window",
    "16": "Move focus to next window (reverse)",
    "17": "Move focus to window drawer",
    "18": "Move focus to status menus",
    "19": "Show help menu",
    "20": "Move focus to next window in app",
    "21": "Move focus to next window in app (reverse)",
    "24": "Launchpad",
    "25": "Show Notification Center",
    "26": "Show Desktop",
    "27": "Application windows",
    "28": "Mission Control",
    "29": "Move left a space",
    "30": "Move right a space",
    "32": "Screenshot (full screen)",
    "33": "Screenshot (window)",
    "34": "Screenshot (selection)",
    "35": "Screenshot (toolbar)",
    "36": "Show accessibility features",
    "37": "Invert colors",
    "38": "Enable Zoom",
    "39": "Zoom in",
    "40": "Zoom out",
    "41": "Switch to virtual desktop 1",
    "42": "Switch to virtual desktop 2",
    "43": "Switch to virtual desktop 3",
    "44": "Switch to virtual desktop 4",
    "56": "Move focus to next control",
    "57": "Move focus to previous control",
    "60": "Show Launchpad",
    "61": "Show Developer Tools",
    "62": "Show Screen Saver",
    "64": "Rotate screen",
    "73": "Show input sources menu",
    "79": "Show Character Viewer",
    "80": "Select previous input source",
    "81": "Select next input source",
    "122": "Show Dictionary",
    "123": "Lookup",
    "160": "Toggle Voice Control",
    "161": "Toggle Switch Control",
    "162": "Toggle Zoom",
    "163": "Toggle Sticky Keys",
    "164": "Toggle Slow Keys",
    "176": "Display brightness down",
    "177": "Display brightness up",
    "180": "Media next",
    "181": "Media play/pause",
    "182": "Media previous",
    "183": "Volume down",
    "184": "Volume up",
    "185": "Mute",
}


def _system_hotkey_name(key_id: str) -> str | None:
    return _SYSTEM_HOTKEY_NAMES.get(key_id)


def _params_to_keys(params: list) -> str:
    if len(params) < 3:
        return ""
    keycode = params[0]
    modifiers = params[2] if len(params) > 2 else 0
    if isinstance(modifiers, str):
        try:
            modifiers = int(modifiers)
        except (ValueError, TypeError):
            return ""
    parts: list[str] = []
    if modifiers & 0x0100:
        parts.append("cmd")
    if modifiers & 0x0200:
        parts.append("alt")
    if modifiers & 0x0400:
        parts.append("ctrl")
    if modifiers & 0x0800:
        parts.append("shift")
    key_name = _keycode_to_name(keycode)
    if key_name:
        parts.append(key_name)
    return "+".join(parts) if parts else ""


_KEYCODE_NAMES: dict[int, str] = {
    0: "a", 1: "s", 2: "d", 3: "f", 4: "h", 5: "g", 6: "z", 7: "x",
    8: "c", 9: "v", 10: "b", 11: "q", 12: "w", 13: "e", 14: "r",
    15: "y", 16: "t", 17: "1", 18: "2", 19: "3", 20: "4", 21: "5",
    22: "6", 23: "7", 24: "8", 25: "9", 26: "0", 27: "minus",
    28: "equal", 29: "]", 30: "o", 31: "u", 32: "[", 33: "i", 34: "p",
    35: "return", 36: "l", 37: "j", 38: "'", 39: "k", 40: ";",
    41: "\\", 42: ",", 43: "/", 44: "n", 45: "m", 46: ".", 47: "tab",
    48: "space", 49: "`", 50: "delete", 51: "escape", 52: "cmd",
    53: "shift", 54: "caps", 55: "alt", 56: "ctrl", 57: "fn",
    96: "f5", 97: "f6", 98: "f7", 99: "f3", 100: "f8", 101: "f9",
    103: "f11", 105: "f13", 107: "f14", 109: "f10", 111: "f12",
    113: "f15", 115: "home", 116: "pageup", 117: "delete",
    118: "f4", 119: "end", 120: "f2", 121: "pagedown", 122: "f1",
    123: "left", 124: "right", 125: "down", 126: "up",
}


def _keycode_to_name(keycode) -> str:
    if isinstance(keycode, str):
        try:
            keycode = int(keycode)
        except (ValueError, TypeError):
            return ""
    if keycode == 65535:
        return ""
    return _KEYCODE_NAMES.get(keycode, str(keycode))


def _normalise_gnome_keys(raw_keys: list[str]) -> str:
    parts: list[str] = []
    for k in raw_keys:
        k = k.strip()
        if not k:
            continue
        k = k.replace("<Control>", "ctrl")
        k = k.replace("<Alt>", "alt")
        k = k.replace("<Super>", "super")
        k = k.replace("<Shift>", "shift")
        k = k.replace("<Primary>", "ctrl")
        k = k.replace("<", "").replace(">", "")
        if k:
            parts.append(k.lower())
    return "+".join(parts) if parts else ""


def _normalise_windows_accel(accel: str) -> str:
    return (
        accel.replace("Ctrl+", "ctrl+")
        .replace("Alt+", "alt+")
        .replace("Shift+", "shift+")
    )


def _normalise_macos_shortcut(char: str, modifiers: Any) -> str:
    parts: list[str] = []
    if modifiers:
        mod_val = modifiers
        if isinstance(mod_val, str):
            mod_val = int(mod_val) if mod_val.isdigit() else 0
        if isinstance(mod_val, int):
            if mod_val & 0x0100:
                parts.append("cmd")
            if mod_val & 0x0200:
                parts.append("alt")
            if mod_val & 0x0400:
                parts.append("ctrl")
            if mod_val & 0x0800:
                parts.append("shift")
    parts.append(char.lower())
    return "+".join(parts)


def _parse_text_shortcuts(path: Path, out: list[ExtractedShortcut]) -> None:
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            action, keys = line.split(":", 1)
            out.append(
                ExtractedShortcut(
                    action=action.strip(),
                    keys=keys.strip(),
                    source=f"file:{path.name}",
                )
            )
        elif "=" in line:
            action, keys = line.split("=", 1)
            out.append(
                ExtractedShortcut(
                    action=action.strip(),
                    keys=keys.strip(),
                    source=f"file:{path.name}",
                )
            )


def _walk_menu_for_accels(
    acc: Any,
    out: list[ExtractedShortcut],
    *,
    depth: int,
    max_depth: int,
    menu_path: str = "",
) -> None:
    if depth > max_depth:
        return
    role = (acc.get_role_name() or "").lower()
    name = acc.get_name() or ""

    if "menu item" in role or "menu" in role:
        try:
            action_if = acc.get_action()
            if action_if:
                for ai in range(action_if.get_n_actions()):
                    key_binding = action_if.get_key_binding(ai)
                    if key_binding:
                        full_path = f"{menu_path} > {name}" if menu_path else name
                        out.append(
                            ExtractedShortcut(
                                action=full_path,
                                keys=_normalise_atspi_accel(key_binding),
                                source="atspi-menu",
                                description=name,
                                platform="linux",
                            )
                        )
        except Exception:
            pass

    try:
        n = acc.get_child_count()
    except Exception:
        return

    for i in range(n):
        try:
            child = acc.get_child_at_index(i)
            if child is None:
                continue
            child_path = f"{menu_path} > {name}" if name and depth > 0 else menu_path
            _walk_menu_for_accels(
                child, out, depth=depth + 1, max_depth=max_depth, menu_path=child_path
            )
        except Exception:
            continue


def _normalise_atspi_accel(accel: str) -> str:
    return (
        accel.replace("<Control>", "ctrl")
        .replace("<Alt>", "alt")
        .replace("<Shift>", "shift")
        .replace("<Primary>", "ctrl")
        .replace("<Meta>", "super")
    )
