from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app_automate.config.models import ShortcutDefinition


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

        elements = macos_ax.list_app_ui_elements(
            app_name, max_depth=15, actionable_only=False
        )
        for el in elements:
            if "menu" not in (el.role or "").lower():
                continue
            cmd_char = getattr(el, "cmd_char", None) or getattr(
                el, "command_char", None
            )
            cmd_mods = getattr(el, "cmd_modifiers", None) or getattr(
                el, "command_modifiers", None
            )
            if cmd_char:
                keys = _normalise_macos_shortcut(cmd_char, cmd_mods)
                shortcuts.append(
                    ExtractedShortcut(
                        action=el.label,
                        keys=keys,
                        source="ax-menu",
                        description=el.label,
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

    return all_shortcuts


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
