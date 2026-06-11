from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app_automate.accessibility.models import UIElement
from app_automate.platform_utils import is_linux

ATSPI_ACTIONABLE_ROLES = {
    "push button",
    "toggle button",
    "check box",
    "radio button",
    "menu item",
    "list item",
    "tree item",
    "tab",
    "combo box",
    "entry",
    "spin button",
    "slider",
    "link",
    "page tab",
}


@dataclass(slots=True)
class ATSPIElement(UIElement):
    @property
    def actionable(self) -> bool:
        role = (self.role or "").lower()
        return role in ATSPI_ACTIONABLE_ROLES


def _ensure_linux() -> None:
    if not is_linux():
        raise RuntimeError("AT-SPI inspection is only available on Linux")


def _ensure_gi_atspi():
    try:
        import gi

        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi

        return Atspi
    except (ImportError, ValueError):
        pass

    import sys

    system_site = "/usr/lib/python3/dist-packages"
    if system_site not in sys.path:
        sys.path.insert(0, system_site)

    try:
        import gi

        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi

        return Atspi
    except (ImportError, ValueError) as exc:
        raise RuntimeError(
            "AT-SPI bindings not available. Install: "
            "sudo apt install python3-gi gir1.2-atspi-2.0. "
            "If using uv, you may need: "
            "uv run --with /usr/lib/python3/dist-packages app-automate ..."
        ) from exc


def list_app_ui_elements(
    app_name: str,
    *,
    max_depth: int = 15,
    actionable_only: bool = False,
) -> list[UIElement]:
    _ensure_linux()
    Atspi = _ensure_gi_atspi()

    desktop = Atspi.get_desktop(0)
    elements: list[UIElement] = []

    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if app is None:
            continue
        app_role = app.get_role_name() or ""
        if app_role != "application":
            continue
        name = app.get_name() or ""
        if app_name.lower() not in name.lower():
            continue
        _walk_atspi(app, elements, max_depth=max_depth, depth=1)

    if actionable_only:
        elements = [e for e in elements if e.actionable and e.has_bounds]
    return elements


def find_matching_elements(
    app_name: str,
    *,
    contains: str,
    max_depth: int = 15,
    actionable_only: bool = True,
    enabled_only: bool = True,
    control_type: str | None = None,
) -> list[UIElement]:
    elements = list_app_ui_elements(
        app_name, max_depth=max_depth, actionable_only=actionable_only
    )
    needle = contains.lower()
    matches = [
        e
        for e in elements
        if needle in e.label.lower()
        or needle in (e.role or "").lower()
        or needle in (e.automation_id or "").lower()
    ]
    if control_type is not None:
        matches = [e for e in matches if e.class_name == control_type]
    if enabled_only:
        matches = [e for e in matches if e.enabled is not False]
    return sorted(
        matches,
        key=lambda e: (
            not e.has_bounds,
            e.depth,
            -((e.width or 0) * (e.height or 0)),
            e.x if e.x is not None else 0,
            e.y if e.y is not None else 0,
        ),
    )


def click_matching_element(
    app_name: str,
    *,
    contains: str,
    max_depth: int = 15,
    index: int = 1,
    control_type: str | None = None,
) -> UIElement:
    elements = find_matching_elements(
        app_name,
        contains=contains,
        max_depth=max_depth,
        actionable_only=True,
        control_type=control_type,
    )
    if not elements:
        raise RuntimeError(f'no AT-SPI elements matched "{contains}" in {app_name}')
    if index < 1 or index > len(elements):
        raise RuntimeError(
            f"match index {index} out of range; found {len(elements)} matches"
        )
    target = elements[index - 1]
    _do_action(target, "click")
    return target


def type_into_matching_element(
    app_name: str,
    *,
    contains: str,
    text: str,
    max_depth: int = 15,
    index: int = 1,
    control_type: str | None = None,
    replace: bool = False,
    interval: float = 0.0,
) -> UIElement:
    elements = find_matching_elements(
        app_name,
        contains=contains,
        max_depth=max_depth,
        actionable_only=True,
        control_type=control_type,
    )
    if not elements:
        raise RuntimeError(f'no AT-SPI elements matched "{contains}" in {app_name}')
    if index < 1 or index > len(elements):
        raise RuntimeError(
            f"match index {index} out of range; found {len(elements)} matches"
        )
    target = elements[index - 1]
    _do_action(target, "focus")
    import pyautogui

    if replace:
        pyautogui.hotkey("ctrl", "a")
    pyautogui.write(text, interval=interval)
    return target


def _do_action(element: UIElement, action_name: str) -> None:
    try:
        Atspi = _ensure_gi_atspi()
    except (ImportError, ValueError):
        from app_automate.adapters.pyautogui_adapter import PyAutoGuiAdapter

        adapter = PyAutoGuiAdapter()
        x = (element.x or 0) + (element.width or 0) / 2.0
        y = (element.y or 0) + (element.height or 0) / 2.0
        adapter.click(x, y)
        return

    desktop = Atspi.get_desktop(0)
    acc = _find_acc_by_path(desktop, element.path)
    if acc is None:
        from app_automate.adapters.pyautogui_adapter import PyAutoGuiAdapter

        adapter = PyAutoGuiAdapter()
        x = (element.x or 0) + (element.width or 0) / 2.0
        y = (element.y or 0) + (element.height or 0) / 2.0
        adapter.click(x, y)
        return

    try:
        action = acc.get_action()
        if action is not None:
            for i in range(action.get_n_actions()):
                name = action.get_name(i) or ""
                if action_name in name.lower() or "click" in name.lower():
                    action.do_action(i)
                    return
    except Exception:
        pass

    from app_automate.adapters.pyautogui_adapter import PyAutoGuiAdapter

    adapter = PyAutoGuiAdapter()
    x = (element.x or 0) + (element.width or 0) / 2.0
    y = (element.y or 0) + (element.height or 0) / 2.0
    adapter.click(x, y)


def _find_acc_by_path(desktop: Any, path: str) -> Any:
    if not path:
        return None
    indices = [int(x) for x in path.split("/") if x]
    current = desktop
    for idx in indices:
        try:
            child = current.get_child_at_index(idx)
            if child is None:
                return None
            current = child
        except Exception:
            return None
    return current


def _walk_atspi(
    acc: Any,
    out: list[UIElement],
    *,
    max_depth: int,
    depth: int,
    path: str = "",
) -> None:
    if depth > max_depth:
        return

    name = acc.get_name() or ""
    role_name = acc.get_role_name() or ""
    desc = acc.get_description() or ""

    x, y, w, h = 0, 0, 0, 0
    try:
        ext = acc.get_extents(0)
        if ext:
            x, y, w, h = ext.x, ext.y, ext.width, ext.height
    except Exception:
        pass

    states: set[str] = set()
    try:
        state_set = acc.get_state_set()
        if state_set:
            raw = state_set.get_states()
            Atspi = _ensure_gi_atspi()
            state_names = [Atspi.StateType.get_name(s) for s in raw]
            states = {n.lower() for n in state_names if n}
    except Exception:
        pass

    enabled = "enabled" in states or "focusable" in states
    child_count = 0
    try:
        child_count = acc.get_child_count()
    except Exception:
        pass

    el = ATSPIElement(
        path=path,
        class_name=role_name,
        role=role_name,
        subrole=None,
        description=desc or None,
        title=None,
        name=name or None,
        x=x,
        y=y,
        width=w,
        height=h,
        enabled=enabled,
        depth=depth,
        child_count=child_count,
        automation_id=None,
    )
    out.append(el)

    try:
        n_children = acc.get_child_count()
    except Exception:
        return

    for i in range(n_children):
        try:
            child = acc.get_child_at_index(i)
            if child is None:
                continue
            child_path = f"{path}/{i}" if path else str(i)
            _walk_atspi(
                child, out, max_depth=max_depth, depth=depth + 1, path=child_path
            )
        except Exception:
            continue
