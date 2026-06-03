from __future__ import annotations

import json
import subprocess
import time

from app_automate.accessibility.models import UIElement
from app_automate.platform_utils import is_macos

ACTIONABLE_CLASSES = {
    "button",
    "checkbox",
    "menu button",
    "pop up button",
    "radio button",
    "text field",
}


class AXElement(UIElement):
    @property
    def actionable(self) -> bool:
        return self.class_name in ACTIONABLE_CLASSES


def list_app_ui_elements(
    app_name: str,
    *,
    max_depth: int = 3,
    actionable_only: bool = False,
    activate: bool = True,
) -> list[AXElement]:
    _ensure_macos()
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
    raw = _osascript(
        app_name,
        "get {class, role description, name, position, size} of front window",
    )
    parts = _parse_csv(raw)
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
    raw = _osascript(
        app_name,
        "get {class, role, subrole, description, title, name, position, size, "
        f"enabled}} of {element_ref}",
    )
    parts = _parse_csv(raw)
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


def _activate_app(app_name: str) -> None:
    result = subprocess.run(
        ["osascript", "-e", f'tell application "{app_name}" to activate'],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def _parse_csv(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",")]


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
