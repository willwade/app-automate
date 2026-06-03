from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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


@dataclass(slots=True)
class UIAElement(UIElement):
    @property
    def actionable(self) -> bool:
        return self.class_name in ACTIONABLE_CONTROL_TYPES


def list_app_ui_elements(
    app_name: str,
    *,
    max_depth: int = 8,
    actionable_only: bool = False,
    visible_bounds_only: bool = False,
) -> list[UIAElement]:
    _ensure_windows()
    automation = _import_uiautomation()
    windows = _safe_children(automation.GetRootControl())
    matching_windows = [
        window for window in windows if _matches_app_window(window, app_name)
    ]
    if not matching_windows:
        raise RuntimeError(f'no visible UIA windows found for app "{app_name}"')

    elements: list[UIAElement] = []
    for index, window in enumerate(matching_windows, start=1):
        window_path = f"window[{index}]"
        root = _to_element(window, path=window_path, depth=0)
        if root is None:
            continue
        elements.append(root)
        elements.extend(
            _walk_children(
                window,
                path=window_path,
                depth=1,
                max_depth=max_depth,
            )
        )

    if visible_bounds_only:
        elements = [element for element in elements if element.has_bounds]
    if actionable_only:
        elements = [element for element in elements if element.actionable]
        elements = [element for element in elements if element.has_bounds]
        return elements
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
    automation = _import_uiautomation()
    matches = _find_matching_controls(
        app_name,
        contains=contains,
        control_type=control_type,
        max_depth=max_depth,
        actionable_only=True,
        enabled_only=True,
    )
    if not matches:
        raise RuntimeError(f'no accessible elements matched "{contains}" in {app_name}')
    if index < 1 or index > len(matches):
        raise RuntimeError(
            f"match index {index} is out of range; found {len(matches)} matches"
        )

    element, control = matches[index - 1]
    _safe_set_focus(control)
    if replace:
        automation.SendKeys("{Ctrl}a{Del}", interval=0.01, waitTime=0.1)
    automation.SendKeys(
        text,
        interval=interval if interval > 0.0 else 0.01,
        waitTime=0.1,
    )
    return element


def click_matching_element(
    app_name: str,
    *,
    contains: str,
    control_type: str | None = None,
    automation_id: str | None = None,
    max_depth: int = 8,
    index: int = 1,
) -> UIAElement:
    matches = _find_matching_controls(
        app_name,
        contains=contains,
        control_type=control_type,
        automation_id=automation_id,
        max_depth=max_depth,
        actionable_only=True,
        enabled_only=True,
    )
    if not matches:
        raise RuntimeError(f'no accessible elements matched "{contains}" in {app_name}')
    if index < 1 or index > len(matches):
        raise RuntimeError(
            f"match index {index} is out of range; found {len(matches)} matches"
        )

    element, control = matches[index - 1]
    _safe_click(control)
    return element


def _walk_children(
    control: Any,
    *,
    path: str,
    depth: int,
    max_depth: int,
) -> list[UIAElement]:
    if depth > max_depth:
        return []

    children = _safe_children(control)
    elements: list[UIAElement] = []
    for index, child in enumerate(children, start=1):
        child_path = f"{path} > child[{index}]"
        element = _to_element(child, path=child_path, depth=depth)
        if element is None:
            continue
        elements.append(element)
        elements.extend(
            _walk_children(
                child,
                path=child_path,
                depth=depth + 1,
                max_depth=max_depth,
            )
        )
    return elements


def _walk_controls(
    control: Any,
    *,
    path: str,
    depth: int,
    max_depth: int,
) -> list[tuple[UIAElement, Any]]:
    if depth > max_depth:
        return []

    children = _safe_children(control)
    elements: list[tuple[UIAElement, Any]] = []
    for index, child in enumerate(children, start=1):
        child_path = f"{path} > child[{index}]"
        element = _to_element(child, path=child_path, depth=depth)
        if element is None:
            continue
        elements.append((element, child))
        elements.extend(
            _walk_controls(
                child,
                path=child_path,
                depth=depth + 1,
                max_depth=max_depth,
            )
        )
    return elements


def _to_element(control: Any, *, path: str, depth: int) -> UIAElement | None:
    try:
        rect = control.BoundingRectangle
    except Exception:
        rect = None

    try:
        child_count = len(_safe_children(control))
    except Exception:
        child_count = 0

    left = _safe_int(getattr(rect, "left", None))
    top = _safe_int(getattr(rect, "top", None))
    right = _safe_int(getattr(rect, "right", None))
    bottom = _safe_int(getattr(rect, "bottom", None))

    width = None
    height = None
    if None not in {left, top, right, bottom}:
        width = right - left
        height = bottom - top

    return UIAElement(
        path=path,
        class_name=_safe_get_str(control, "ControlTypeName")
        or _safe_get_str(control, "ClassName")
        or "UnknownControl",
        role=_safe_get_str(control, "LocalizedControlType"),
        subrole=_safe_get_str(control, "ClassName"),
        description=_safe_get_str(control, "HelpText"),
        title=None,
        name=_safe_get_str(control, "Name"),
        automation_id=_safe_get_str(control, "AutomationId"),
        x=left,
        y=top,
        width=width,
        height=height,
        enabled=_safe_get_bool(control, "IsEnabled"),
        depth=depth,
        child_count=child_count,
    )


def _matches_app_window(control: Any, app_name: str) -> bool:
    name = _safe_get_str(control, "Name") or ""
    class_name = _safe_get_str(control, "ClassName") or ""
    automation_id = _safe_get_str(control, "AutomationId") or ""
    process_name = _safe_process_name(control)
    needle = app_name.lower()
    return any(
        needle in value.lower()
        for value in (name, class_name, automation_id, process_name)
        if value
    )


def _safe_process_name(control: Any) -> str | None:
    return _safe_get_str(control, "ProcessName")


def _matches_element(element: UIAElement, needle: str) -> bool:
    haystacks = [
        element.label,
        element.class_name,
        element.role or "",
        element.subrole or "",
        element.automation_id or "",
    ]
    return any(needle in value.lower() for value in haystacks if value)


def _find_matching_controls(
    app_name: str,
    *,
    contains: str,
    control_type: str | None,
    automation_id: str | None = None,
    max_depth: int,
    actionable_only: bool,
    enabled_only: bool,
) -> list[tuple[UIAElement, Any]]:
    _ensure_windows()
    automation = _import_uiautomation()
    windows = _safe_children(automation.GetRootControl())
    matching_windows = [
        window for window in windows if _matches_app_window(window, app_name)
    ]
    if not matching_windows:
        raise RuntimeError(f'no visible UIA windows found for app "{app_name}"')

    needle = contains.lower()
    matches: list[tuple[UIAElement, Any]] = []
    for index, window in enumerate(matching_windows, start=1):
        window_path = f"window[{index}]"
        for element, control in _walk_controls(
            window,
            path=window_path,
            depth=1,
            max_depth=max_depth,
        ):
            if actionable_only and (not element.actionable or not element.has_bounds):
                continue
            if not _matches_element(element, needle):
                continue
            if control_type is not None and element.class_name != control_type:
                continue
            if automation_id is not None and element.automation_id != automation_id:
                continue
            if enabled_only and element.enabled is False:
                continue
            matches.append((element, control))

    return sorted(
        matches,
        key=lambda match: (
            not match[0].has_bounds,
            not bool(match[0].automation_id),
            match[0].label.lower() != needle,
            match[0].depth,
            -((match[0].width or 0) * (match[0].height or 0)),
            match[0].x if match[0].x is not None else 0,
            match[0].y if match[0].y is not None else 0,
        ),
    )


def _clear_comtypes_gen_cache() -> None:
    try:
        import shutil

        import comtypes.client

        gen_dir = comtypes.client.gen_dir
        if gen_dir:
            for entry in gen_dir.iterdir():
                if entry.name == "__init__.py":
                    continue
                try:
                    if entry.is_dir():
                        shutil.rmtree(entry)
                    else:
                        entry.unlink()
                except Exception:
                    pass
    except Exception:
        pass


def _import_uiautomation() -> Any:
    _clear_comtypes_gen_cache()
    try:
        import uiautomation as automation
    except ImportError as exc:
        raise RuntimeError(
            "Windows UIA support requires the optional 'uiautomation' package"
        ) from exc
    return automation


def _safe_children(control: Any) -> list[Any]:
    try:
        return list(control.GetChildren())
    except Exception:
        return []


def _safe_get(control: Any, attribute: str) -> object:
    try:
        return getattr(control, attribute)
    except Exception:
        return None


def _safe_get_str(control: Any, attribute: str) -> str | None:
    return _safe_str(_safe_get(control, attribute))


def _safe_get_bool(control: Any, attribute: str) -> bool | None:
    return _safe_bool(_safe_get(control, attribute))


def _safe_set_focus(control: Any) -> None:
    try:
        control.SetFocus()
    except Exception as exc:
        raise RuntimeError("failed to focus target UIA element") from exc


def _safe_click(control: Any) -> None:
    try:
        invoke = getattr(control, "GetInvokePattern", None)
        if invoke is not None:
            pattern = invoke()
            if pattern is not None:
                pattern.Invoke()
                return
        control.Click()
    except Exception as exc:
        raise RuntimeError("failed to invoke target UIA element") from exc


def _safe_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_bool(value: object) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _ensure_windows() -> None:
    if not is_windows():
        raise RuntimeError("Windows UIA inspection is only available on Windows")
