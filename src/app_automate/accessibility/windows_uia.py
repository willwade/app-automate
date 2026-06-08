from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app_automate.accessibility.models import UIElement
from app_automate.platform_utils import is_windows

ACTIONABLE_CONTROL_TYPES = {
    "ButtonControl",
    "CheckBoxControl",
    "ComboBoxControl",
    "EditControl",
    "HyperlinkControl",
    "ListItemControl",
    "MenuItemControl",
    "RadioButtonControl",
    "SplitButtonControl",
    "TabItemControl",
    "TreeItemControl",
}

ACTIONABLE_ROLES = {
    "button",
    "checkbox",
    "combobox",
    "edit",
    "hyperlink",
    "list item",
    "menu item",
    "radio button",
    "split button",
    "tab item",
    "tree item",
}


@dataclass(slots=True)
class UIAElement(UIElement):
    accelerator_key: str | None = None

    @property
    def actionable(self) -> bool:
        if self.class_name in ACTIONABLE_CONTROL_TYPES:
            return True
        return (self.role or "").lower() in ACTIONABLE_ROLES


_UIA_TOOL_PATH: Path | None = None


def _find_uia_tool() -> Path:
    global _UIA_TOOL_PATH
    if _UIA_TOOL_PATH is not None and _UIA_TOOL_PATH.exists():
        return _UIA_TOOL_PATH
    repo_root = Path(__file__).resolve().parents[3]
    candidate = repo_root / "native" / "uia-tool" / "publish" / "uia.exe"
    if candidate.exists():
        _UIA_TOOL_PATH = candidate
        return candidate
    found = shutil.which("uia")
    if found:
        _UIA_TOOL_PATH = Path(found)
        return _UIA_TOOL_PATH
    raise RuntimeError(
        "uia.exe not found. "
        "Build: dotnet publish native/uia-tool -c Release -o native/uia-tool/publish"
    )


def _uia_tool(*args: str, timeout: float = 30) -> str:
    binary = _find_uia_tool()
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


def _uia_tool_item_to_element(item: dict) -> UIAElement:
    return UIAElement(
        path=item.get("path", ""),
        class_name=item.get("class_name", ""),
        role=item.get("role"),
        subrole=item.get("subrole"),
        description=None,
        title=None,
        name=item.get("name"),
        automation_id=item.get("automation_id"),
        x=item.get("x"),
        y=item.get("y"),
        width=item.get("width"),
        height=item.get("height"),
        enabled=item.get("enabled"),
        depth=item.get("depth", 0),
        child_count=item.get("child_count", 0),
        accelerator_key=item.get("accelerator_key"),
    )


def list_app_ui_elements(
    app_name: str,
    *,
    max_depth: int = 8,
    actionable_only: bool = False,
    visible_bounds_only: bool = False,
) -> list[UIAElement]:
    _ensure_windows()
    cmd_args = ["list", app_name, "--max-depth", str(max_depth), "--json"]
    if actionable_only:
        cmd_args.append("--actionable")
    raw = _uia_tool(*cmd_args)
    items = json.loads(raw) if raw else []
    elements = [_uia_tool_item_to_element(item) for item in items]
    if visible_bounds_only:
        elements = [e for e in elements if e.has_bounds]
    return elements


def find_matching_elements(
    app_name: str,
    *,
    contains: str,
    control_type: str | None = None,
    automation_id: str | None = None,
    max_depth: int = 8,
    actionable_only: bool = True,
    enabled_only: bool = True,
) -> list[UIAElement]:
    needle = contains.lower()
    elements = list_app_ui_elements(
        app_name,
        max_depth=max_depth,
        actionable_only=actionable_only,
        visible_bounds_only=actionable_only,
    )
    matches = [
        element
        for element in elements
        if _matches_element(element, needle)
        and (control_type is None or element.class_name == control_type)
        and (automation_id is None or element.automation_id == automation_id)
        and (not enabled_only or element.enabled is not False)
    ]
    return sorted(
        matches,
        key=lambda element: (
            not element.has_bounds,
            not bool(element.automation_id),
            element.label.lower() != needle,
            element.depth,
            -((element.width or 0) * (element.height or 0)),
            element.x if element.x is not None else 0,
            element.y if element.y is not None else 0,
        ),
    )


def type_into_matching_element(
    app_name: str,
    *,
    contains: str,
    text: str,
    control_type: str | None = None,
    max_depth: int = 12,
    index: int = 1,
    replace: bool = False,
    interval: float = 0.0,
) -> UIAElement:
    _ensure_windows()
    elements = find_matching_elements(
        app_name,
        contains=contains,
        actionable_only=True,
        enabled_only=True,
    )
    if not elements:
        raise RuntimeError(f'no accessible elements matched "{contains}" in {app_name}')
    if index < 1 or index > len(elements):
        raise RuntimeError(
            f"match index {index} is out of range; found {len(elements)} matches"
        )
    target = elements[index - 1]
    _uia_tool("type", app_name, contains, text, timeout=15)
    return target


def click_matching_element(
    app_name: str,
    *,
    contains: str,
    control_type: str | None = None,
    automation_id: str | None = None,
    max_depth: int = 8,
    index: int = 1,
) -> UIAElement:
    _ensure_windows()
    elements = find_matching_elements(
        app_name,
        contains=contains,
        automation_id=automation_id,
        actionable_only=True,
        enabled_only=True,
    )
    if not elements:
        raise RuntimeError(f'no accessible elements matched "{contains}" in {app_name}')
    if index < 1 or index > len(elements):
        raise RuntimeError(
            f"match index {index} is out of range; found {len(elements)} matches"
        )
    target = elements[index - 1]
    search = automation_id if automation_id else contains
    _uia_tool("click", app_name, search, timeout=15)
    return target


def _matches_element(element: UIAElement, needle: str) -> bool:
    haystacks = [
        element.label,
        element.class_name,
        element.role or "",
        element.subrole or "",
        element.automation_id or "",
    ]
    return any(needle in value.lower() for value in haystacks if value)


def _ensure_windows() -> None:
    if not is_windows():
        raise RuntimeError("Windows UIA inspection is only available on Windows")
