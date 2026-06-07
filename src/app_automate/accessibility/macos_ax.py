from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from app_automate.accessibility.models import UIElement
from app_automate.platform_utils import is_macos

ACTIONABLE_CLASSES = {
    "button",
    "checkbox",
    "menu button",
    "pop up button",
    "radio button",
    "text area",
    "text field",
}

_AXTOLl_PATH: Path | None = None


class AXElement(UIElement):
    @property
    def actionable(self) -> bool:
        return self.class_name in ACTIONABLE_CLASSES


def _find_axtool() -> Path | None:
    global _AXTOLl_PATH
    if _AXTOLl_PATH is not None:
        return _AXTOLl_PATH if _AXTOLl_PATH.exists() else None
    repo_root = Path(__file__).resolve().parents[3]
    candidate = repo_root / "native" / "axtool" / ".build" / "debug" / "axtool"
    if candidate.exists():
        _AXTOLl_PATH = candidate
        return candidate
    found = shutil.which("axtool")
    if found:
        _AXTOLl_PATH = Path(found)
        return _AXTOLl_PATH
    return None


def _has_axtool() -> bool:
    return _find_axtool() is not None


def _axtool(*args: str, timeout: float = 30) -> str:
    binary = _find_axtool()
    if binary is None:
        raise RuntimeError("axtool not found")
    result = subprocess.run(
        [str(binary), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def list_app_ui_elements(
    app_name: str,
    *,
    max_depth: int = 3,
    actionable_only: bool = False,
    activate: bool = True,
) -> list[AXElement]:
    _ensure_macos()
    if _has_axtool():
        return _list_via_axtool(
            app_name,
            max_depth=max_depth,
            actionable_only=actionable_only,
            activate=activate,
        )
    return _list_via_osascript(
        app_name,
        max_depth=max_depth,
        actionable_only=actionable_only,
        activate=activate,
    )


def _list_via_axtool(
    app_name: str,
    *,
    max_depth: int,
    actionable_only: bool,
    activate: bool,
) -> list[AXElement]:
    cmd_args = ["list", "--app", app_name, "--max-depth", str(max_depth), "--json"]
    if actionable_only:
        cmd_args.append("--actionable")
    if activate:
        _axtool("activate", "--app", app_name)
        time.sleep(0.3)
    raw = _axtool(*cmd_args)
    items = json.loads(raw) if raw else []
    return [_axtool_item_to_element(item) for item in items]


def _axtool_item_to_element(item: dict) -> AXElement:
    return AXElement(
        path=item.get("path", ""),
        class_name=item.get("class_name", ""),
        role=item.get("role"),
        subrole=item.get("subrole"),
        description=item.get("description"),
        title=item.get("title"),
        name=item.get("name"),
        x=item.get("x"),
        y=item.get("y"),
        width=item.get("width"),
        height=item.get("height"),
        enabled=item.get("enabled"),
        depth=item.get("depth", 0),
        child_count=item.get("child_count", 0),
    )


def _list_via_osascript(
    app_name: str,
    *,
    max_depth: int,
    actionable_only: bool,
    activate: bool,
) -> list[AXElement]:
    if activate:
        _activate_app(app_name)
        time.sleep(0.4)
    if _window_count(app_name) == 0:
        raise RuntimeError(f'no visible windows found for app "{app_name}"')

    elements = [_window_element(app_name)]
    elements.extend(
        _walk_children(
            app_name,
            parent_ref="front window",
            path="front window",
            depth=1,
            max_depth=max_depth,
        )
    )
    if actionable_only:
        return [element for element in elements if element.actionable]
    return elements


def list_app_ui_elements_json(
    app_name: str,
    *,
    max_depth: int = 3,
    actionable_only: bool = False,
    activate: bool = True,
) -> str:
    elements = list_app_ui_elements(
        app_name,
        max_depth=max_depth,
        actionable_only=actionable_only,
        activate=activate,
    )
    return json.dumps([element.as_dict() for element in elements], indent=2)


def find_matching_elements(
    app_name: str,
    *,
    contains: str,
    max_depth: int = 3,
    actionable_only: bool = True,
    enabled_only: bool = True,
    activate: bool = True,
) -> list[AXElement]:
    needle = contains.lower()
    elements = list_app_ui_elements(
        app_name,
        max_depth=max_depth,
        actionable_only=actionable_only,
        activate=activate,
    )
    matches = [
        element
        for element in elements
        if _matches_element(element, needle)
        and (not enabled_only or element.enabled is not False)
    ]
    return sorted(
        matches,
        key=lambda element: (
            element.label.lower() != needle,
            element.depth,
            element.x if element.x is not None else 0,
            element.y if element.y is not None else 0,
        ),
    )


def extract_menu_shortcuts(app_name: str) -> list[dict[str, object]]:
    _ensure_macos()
    if _has_axtool():
        return _shortcuts_via_axtool(app_name)
    return _shortcuts_via_osascript(app_name)


def _shortcuts_via_axtool(app_name: str) -> list[dict[str, object]]:
    raw = _axtool("shortcuts", "--app", app_name, timeout=10)
    items = json.loads(raw) if raw else []
    return [
        {
            "action": item["action"],
            "cmd_char": item["cmdChar"],
            "cmd_modifiers": str(item.get("cmdModifiers", "")),
            "description": item["description"],
        }
        for item in items
    ]


def _shortcuts_via_osascript(app_name: str) -> list[dict[str, object]]:
    _activate_app(app_name)
    time.sleep(0.3)
    script = (
        f'tell application "System Events" to tell process "{app_name}"\n'
        '    set _out to ""\n'
        "    set _mb to menu bar 1\n"
        "    repeat with _bi from 1 to (count menu bar items of _mb)\n"
        "        set _barItem to menu bar item _bi of _mb\n"
        "        set _barTitle to name of _barItem\n"
        "        try\n"
        "            set _menu to menu 1 of _barItem\n"
        "            repeat with _i from 1 to (count menu items of _menu)\n"
        "                set _mi to menu item _i of _menu\n"
        '                set _title to ""\n'
        "                try\n"
        "                    set _title to name of _mi\n"
        "                end try\n"
        '                set _cmdChar to ""\n'
        "                try\n"
        '                    set _cmdChar to value of attribute '
        '"AXMenuItemCmdChar" of _mi\n'
        '                    if _cmdChar is missing value '
        'then set _cmdChar to ""\n'
        "                end try\n"
        '                set _cmdMods to ""\n'
        "                try\n"
        '                    set _cmdMods to value of attribute '
        '"AXMenuItemCmdModifiers" of _mi\n'
        '                    if _cmdMods is missing value '
        'then set _cmdMods to ""\n'
        "                end try\n"
        '                if _cmdChar is not "" then\n'
        "                    set _out to _out & _barTitle & "
        '"|" & _title & "|" & _cmdChar & "|" '
        '& (_cmdMods as text) & "||"\n'
        "                end if\n"
        "            end repeat\n"
        "        end try\n"
        "    end repeat\n"
        "    return _out\n"
        "end tell"
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        return []
    raw = result.stdout.strip()
    if not raw:
        return []
    shortcuts: list[dict[str, object]] = []
    for entry in raw.split("||"):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split("|")
        if len(parts) < 3:
            continue
        shortcuts.append(
            {
                "action": f"{parts[0]} > {parts[1]}",
                "cmd_char": parts[2],
                "cmd_modifiers": parts[3] if len(parts) > 3 else "",
                "description": parts[1],
            }
        )
    return shortcuts


# --- osascript fallback helpers ---


def _walk_children(
    app_name: str,
    *,
    parent_ref: str,
    path: str,
    depth: int,
    max_depth: int,
) -> list[AXElement]:
    if depth > max_depth:
        return []

    try:
        child_count = _count_children(app_name, parent_ref)
    except RuntimeError:
        return []
    elements: list[AXElement] = []
    for index in range(1, child_count + 1):
        child_ref = f"UI element {index} of {parent_ref}"
        child_path = f"{path} > UI element {index}"
        try:
            element = _element_info(app_name, child_ref, child_path, depth)
        except RuntimeError:
            continue
        elements.append(element)
        elements.extend(
            _walk_children(
                app_name,
                parent_ref=child_ref,
                path=child_path,
                depth=depth + 1,
                max_depth=max_depth,
            )
        )
    return elements


def _window_element(app_name: str) -> AXElement:
    parts = _osascript_list(
        app_name,
        "class, role description, name, position, size",
        "front window",
    )
    return AXElement(
        path="front window",
        class_name=parts[0],
        role=parts[1],
        subrole=None,
        description=None,
        title=None,
        name=_clean_value(parts[2]),
        x=_parse_int(parts[3]),
        y=_parse_int(parts[4]),
        width=_parse_int(parts[5]),
        height=_parse_int(parts[6]),
        enabled=True,
        depth=0,
        child_count=_count_children(app_name, "front window"),
    )


def _element_info(
    app_name: str,
    element_ref: str,
    path: str,
    depth: int,
) -> AXElement:
    parts = _osascript_list(
        app_name,
        "class, role, subrole, description, title, name, position, size, enabled",
        element_ref,
    )
    return AXElement(
        path=path,
        class_name=parts[0],
        role=_clean_value(parts[1]),
        subrole=_clean_value(parts[2]),
        description=_clean_value(parts[3]),
        title=_clean_value(parts[4]),
        name=_clean_value(parts[5]),
        x=_parse_int(parts[6]),
        y=_parse_int(parts[7]),
        width=_parse_int(parts[8]),
        height=_parse_int(parts[9]),
        enabled=_parse_bool(parts[10]),
        depth=depth,
        child_count=_count_children(app_name, element_ref),
    )


def _count_children(app_name: str, element_ref: str) -> int:
    raw = _osascript(app_name, f"count UI elements of {element_ref}")
    return _parse_int(raw) or 0


def _window_count(app_name: str) -> int:
    raw = _osascript(app_name, "count windows")
    return _parse_int(raw) or 0


def _osascript(app_name: str, command: str) -> str:
    script = (
        f'tell application "System Events" to tell process "{app_name}" to {command}'
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def _osascript_list(app_name: str, properties: str, element_ref: str) -> list[str]:
    script = (
        'set _delim to "|||"\n'
        'set AppleScript\'s text item delimiters to _delim\n'
        f'tell application "System Events" to tell process "{app_name}" '
        f"to set _raw to {{{properties}}} of {element_ref}\n"
        "set _out to \"\"\n"
        "repeat with _i from 1 to (length of _raw)\n"
        "    set _v to item _i of _raw\n"
        "    if (class of _v is list) then\n"
        "        repeat with _j from 1 to (length of _v)\n"
        '            set _out to _out & (item _j of _v as text) & "|||"\n'
        "        end repeat\n"
        "    else\n"
        '        set _out to _out & (_v as text) & "|||"\n'
        "    end if\n"
        "end repeat\n"
        "set AppleScript's text item delimiters to \"\"\n"
        "return _out"
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    raw = result.stdout.strip()
    parts = raw.split("|||")
    return [p.strip() for p in parts[:-1]]


def _activate_app(app_name: str) -> None:
    result = subprocess.run(
        ["osascript", "-e", f'tell application "{app_name}" to activate'],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def _matches_element(element: AXElement, needle: str) -> bool:
    haystacks = [
        element.label,
        element.class_name,
        element.role or "",
        element.subrole or "",
    ]
    return any(needle in value.lower() for value in haystacks if value)


def _clean_value(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or stripped == "missing value":
        return None
    return stripped


def _parse_int(value: str | None) -> int | None:
    cleaned = _clean_value(value)
    if cleaned is None:
        return None
    return int(cleaned)


def _parse_bool(value: str | None) -> bool | None:
    cleaned = _clean_value(value)
    if cleaned is None:
        return None
    return cleaned.lower() == "true"


def _ensure_macos() -> None:
    if not is_macos():
        raise RuntimeError("macOS accessibility inspection is only available on macOS")
