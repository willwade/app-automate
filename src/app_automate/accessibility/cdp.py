from __future__ import annotations

import json
import subprocess
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Generator

from app_automate.accessibility.models import UIElement
from app_automate.platform_utils import is_windows

CDP_INTERACTIVE_ROLES = {
    "button",
    "link",
    "menuitem",
    "tab",
    "textbox",
    "combobox",
    "searchbox",
    "menuitemcheckbox",
    "menuitemradio",
    "treeitem",
    "checkbox",
    "radio",
    "slider",
    "spinbutton",
    "switch",
}

CDP_DEFAULT_PORT = 9222


@dataclass(slots=True)
class CDPElement(UIElement):
    @property
    def actionable(self) -> bool:
        return self.role in CDP_INTERACTIVE_ROLES


def ensure_cdp_enabled(app_name: str) -> dict[str, str]:
    _ensure_windows()
    info = _check_cdp_status()
    if info["listening"] == "true":
        return info
    return _enable_cdp_for_app(app_name)


def cdp_status() -> dict[str, str]:
    _ensure_windows()
    return _check_cdp_status()


def _match_text(haystack: str, needle: str, exact: bool) -> bool:
    if exact:
        return haystack.lower() == needle.lower()
    return needle.lower() in haystack.lower()


def list_cdp_elements(
    port: int = CDP_DEFAULT_PORT,
    *,
    actionable_only: bool = False,
    contains: str | None = None,
    exact: bool = False,
) -> list[UIElement]:
    _ensure_windows()
    with cdp_session(port) as page:
        elements = _collect_elements(page)
    if actionable_only:
        elements = [e for e in elements if e.actionable and e.has_bounds]
    if contains is not None:
        elements = [
            e
            for e in elements
            if _match_text(e.label, contains, exact)
            or _match_text(e.role or "", contains, exact)
            or _match_text(e.description or "", contains, exact)
        ]
    return elements


def find_cdp_elements(
    *,
    contains: str,
    port: int = CDP_DEFAULT_PORT,
    actionable_only: bool = True,
    enabled_only: bool = True,
    exact: bool = False,
) -> list[UIElement]:
    elements = list_cdp_elements(port, actionable_only=actionable_only)
    matches = [
        e
        for e in elements
        if _match_text(e.label, contains, exact)
        or _match_text(e.role or "", contains, exact)
        or _match_text(e.description or "", contains, exact)
    ]
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


def click_cdp_element(
    *,
    contains: str,
    port: int = CDP_DEFAULT_PORT,
    index: int = 1,
    exact: bool = False,
    selector: str | None = None,
) -> UIElement:
    with cdp_session(port) as page:
        if selector:
            locator = page.locator(selector)
            if locator.count() > 0:
                el = locator.first
                box = el.bounding_box()
                role = el.get_attribute("role") or ""
                name = el.get_attribute("aria-label") or ""
                if not name:
                    try:
                        name = el.inner_text().strip()
                    except Exception:
                        name = ""
                locator.first.click()
                if box:
                    return CDPElement(
                        path="cdp-selector",
                        class_name=role,
                        role=role,
                        subrole=None,
                        description=None,
                        title=None,
                        name=name or None,
                        x=int(round(box["x"])),
                        y=int(round(box["y"])),
                        width=int(round(box["width"])),
                        height=int(round(box["height"])),
                        enabled=True,
                        depth=0,
                        child_count=0,
                        automation_id=None,
                    )
        elements = _collect_elements(page)
        candidates = [
            e
            for e in elements
            if e.actionable
            and e.has_bounds
            and e.enabled is not False
            and (
                _match_text(e.label, contains, exact)
                or _match_text(e.role or "", contains, exact)
            )
        ]
        if not candidates:
            raise RuntimeError(f'no CDP elements matched "{contains}"')
        candidates.sort(
            key=lambda e: (
                e.depth,
                -((e.width or 0) * (e.height or 0)),
            ),
        )
        if index < 1 or index > len(candidates):
            raise RuntimeError(
                f"match index {index} out of range; found {len(candidates)} matches"
            )
        target = candidates[index - 1]
        clicked = False
        aria_locator = page.locator(f'[aria-label="{target.label}"]')
        if aria_locator.count() > 0:
            aria_locator.first.click()
            clicked = True
        if not clicked and target.name:
            tag_map = {
                "button": "button",
                "link": "a",
                "combobox": "select",
            }
            tag = tag_map.get(target.role or "")
            text = target.name.strip()
            if tag and text:
                text_locator = page.locator(f"{tag} >> text={text}")
                if text_locator.count() > 0:
                    text_locator.first.click()
                    clicked = True
        if not clicked:
            cx = (target.x or 0) + (target.width or 0) // 2
            cy = (target.y or 0) + (target.height or 0) // 2
            page.mouse.click(cx, cy)
    return target


def type_into_cdp_element(
    *,
    contains: str,
    text: str,
    port: int = CDP_DEFAULT_PORT,
    index: int = 1,
    replace: bool = False,
    exact: bool = False,
    selector: str | None = None,
) -> UIElement:
    with cdp_session(port) as page:
        if selector:
            locator = page.locator(selector)
            if locator.count() > 0:
                el = locator.first
                box = el.bounding_box()
                role = el.get_attribute("role") or ""
                name = el.get_attribute("aria-label") or ""
                if not name:
                    try:
                        name = el.inner_text().strip()
                    except Exception:
                        name = ""
                _type_into_page_element_direct(page, el, text, replace=replace)
                if box:
                    return CDPElement(
                        path="cdp-selector",
                        class_name=role or "textbox",
                        role=role or "textbox",
                        subrole=None,
                        description=None,
                        title=None,
                        name=name or None,
                        x=int(round(box["x"])),
                        y=int(round(box["y"])),
                        width=int(round(box["width"])),
                        height=int(round(box["height"])),
                        enabled=True,
                        depth=0,
                        child_count=0,
                        automation_id=None,
                    )
        elements = _collect_elements(page)
        candidates = [
            e
            for e in elements
            if e.actionable
            and e.has_bounds
            and e.enabled is not False
            and (
                _match_text(e.label, contains, exact)
                or _match_text(e.role or "", contains, exact)
            )
            and e.role
            in (
                "textbox",
                "combobox",
                "searchbox",
                "button",
            )
        ]
        if not candidates:
            raise RuntimeError(f'no CDP text fields matched "{contains}"')
        candidates.sort(
            key=lambda e: (
                e.role == "button",
                e.depth,
                -((e.width or 0) * (e.height or 0)),
            ),
        )
        if index < 1 or index > len(candidates):
            raise RuntimeError(
                f"match index {index} out of range; found {len(candidates)} matches"
            )
        target = candidates[index - 1]
        _type_into_page_element(page, target, text, replace=replace)
    return target


def _type_into_page_element(
    page: Any, target: UIElement, text: str, *, replace: bool
) -> None:
    aria = target.label
    locator = page.locator(f'[aria-label="{aria}"]')
    if locator.count() == 0:
        cx = (target.x or 0) + (target.width or 0) // 2
        cy = (target.y or 0) + (target.height or 0) // 2
        page.mouse.click(cx, cy)
        page.wait_for_timeout(300)
        if replace:
            page.keyboard.press("Control+a")
        page.keyboard.type(text, delay=10)
        return
    el = locator.first
    tag = el.evaluate("e => e.tagName")
    if tag in ("INPUT", "TEXTAREA"):
        if replace:
            el.fill(text)
        else:
            el.click()
            page.keyboard.type(text, delay=10)
    else:
        el.click()
        page.wait_for_timeout(300)
        if replace:
            page.keyboard.press("Control+a")
        page.keyboard.type(text, delay=10)


def _type_into_page_element_direct(
    page: Any, el: Any, text: str, *, replace: bool
) -> None:
    tag = el.evaluate("e => e.tagName")
    if tag in ("INPUT", "TEXTAREA"):
        if replace:
            el.fill(text)
        else:
            el.click()
            page.keyboard.type(text, delay=10)
    else:
        el.click()
        page.wait_for_timeout(300)
        if replace:
            page.keyboard.press("Control+a")
        page.keyboard.type(text, delay=10)


@contextmanager
def cdp_session(
    port: int = CDP_DEFAULT_PORT,
) -> Generator[Any, None, None]:
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(f"http://localhost:{port}")
    page = browser.contexts[0].pages[0]
    try:
        yield page
    finally:
        try:
            browser.close()
        except Exception:
            pass
        try:
            pw.stop()
        except Exception:
            pass


def _collect_elements(page: Any) -> list[UIElement]:
    elements: list[UIElement] = []
    seen: set[str] = set()

    role_selectors = ", ".join(f'[role="{r}"]' for r in CDP_INTERACTIVE_ROLES)
    locator = page.locator(role_selectors)
    count = locator.count()
    for i in range(count):
        try:
            el = locator.nth(i)
            if not el.is_visible():
                continue
            box = el.bounding_box()
            if box is None:
                continue
            role = el.get_attribute("role") or ""
            name = el.get_attribute("aria-label") or ""
            if not name:
                try:
                    name = el.inner_text().strip()
                except Exception:
                    name = ""
            title = el.get_attribute("title") or ""
            disabled = el.is_disabled()
            tag = el.evaluate("e => e.tagName")
            key = f"{role}:{name}:{box['x']}:{box['y']}"
            if key in seen:
                continue
            seen.add(key)
            elements.append(
                CDPElement(
                    path=f"cdp[{i}]",
                    class_name=role,
                    role=role,
                    subrole=tag.lower(),
                    description=title or None,
                    title=None,
                    name=name or None,
                    x=int(round(box["x"])),
                    y=int(round(box["y"])),
                    width=int(round(box["width"])),
                    height=int(round(box["height"])),
                    enabled=not disabled,
                    depth=0,
                    child_count=0,
                    automation_id=None,
                )
            )
        except Exception:
            continue

    input_locator = page.locator(
        'input:not([type="hidden"]), textarea, [contenteditable="true"]'
    )
    input_count = input_locator.count()
    for i in range(input_count):
        try:
            el = input_locator.nth(i)
            if not el.is_visible():
                continue
            box = el.bounding_box()
            if box is None:
                continue
            aria = el.get_attribute("aria-label") or ""
            placeholder = el.get_attribute("placeholder") or ""
            tag = el.evaluate("e => e.tagName")
            role = el.get_attribute("role") or ""
            if not role:
                role = "textbox"
            disabled = el.is_disabled()
            label = aria or placeholder or tag.lower()
            key = f"{role}:{label}:{box['x']}:{box['y']}"
            if key in seen:
                continue
            seen.add(key)
            elements.append(
                CDPElement(
                    path=f"cdp-input[{i}]",
                    class_name=role,
                    role=role,
                    subrole=tag.lower(),
                    description=placeholder or None,
                    title=None,
                    name=label or None,
                    x=int(round(box["x"])),
                    y=int(round(box["y"])),
                    width=int(round(box["width"])),
                    height=int(round(box["height"])),
                    enabled=not disabled,
                    depth=0,
                    child_count=0,
                    automation_id=None,
                )
            )
        except Exception:
            continue

    native_locator = page.locator(
        "button:not([role]), a[href]:not([role]), select:not([role]), "
        "summary:not([role]), details:not([role])"
    )
    native_count = native_locator.count()
    for i in range(native_count):
        try:
            el = native_locator.nth(i)
            if not el.is_visible():
                continue
            box = el.bounding_box()
            if box is None:
                continue
            tag = el.evaluate("e => e.tagName")
            native_role_map = {
                "BUTTON": "button",
                "A": "link",
                "SELECT": "combobox",
                "SUMMARY": "button",
                "DETAILS": "group",
            }
            role = native_role_map.get(tag, tag.lower())
            aria = el.get_attribute("aria-label") or ""
            name = aria
            if not name:
                try:
                    name = el.inner_text().strip()
                except Exception:
                    name = ""
            title = el.get_attribute("title") or ""
            disabled = el.is_disabled()
            label = name or title or tag.lower()
            key = f"{role}:{label}:{box['x']}:{box['y']}"
            if key in seen:
                continue
            seen.add(key)
            elements.append(
                CDPElement(
                    path=f"cdp-native[{i}]",
                    class_name=role,
                    role=role,
                    subrole=tag.lower(),
                    description=title or None,
                    title=None,
                    name=label or None,
                    x=int(round(box["x"])),
                    y=int(round(box["y"])),
                    width=int(round(box["width"])),
                    height=int(round(box["height"])),
                    enabled=not disabled,
                    depth=0,
                    child_count=0,
                    automation_id=None,
                )
            )
        except Exception:
            continue

    return elements


def _check_cdp_status() -> dict[str, str]:
    try:
        with urllib.request.urlopen(
            f"http://localhost:{CDP_DEFAULT_PORT}/json", timeout=1
        ) as resp:
            targets = json.loads(resp.read())
            pages = [t for t in targets if t.get("type") == "page"]
            if pages:
                return {
                    "listening": "true",
                    "port": str(CDP_DEFAULT_PORT),
                    "page_title": pages[0].get("title", ""),
                    "page_url": pages[0].get("url", ""),
                }
            return {
                "listening": "true",
                "port": str(CDP_DEFAULT_PORT),
                "page_title": "",
                "page_url": "",
            }
    except Exception:
        return {"listening": "false", "port": str(CDP_DEFAULT_PORT)}


def _enable_cdp_for_app(app_name: str) -> dict[str, str]:
    import os

    env_var = "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"
    env_value = f"--remote-debugging-port={CDP_DEFAULT_PORT}"

    _set_user_env_var(env_var, env_value)

    pids = _find_app_pids(app_name)
    if pids:
        for pid in pids:
            subprocess.run(["taskkill", "/f", "/pid", str(pid)], capture_output=True)

        env = os.environ.copy()
        env[env_var] = env_value
        exe_path = _find_app_exe(app_name)
        if exe_path:
            subprocess.Popen([exe_path], env=env)

    return {
        "listening": "pending",
        "port": str(CDP_DEFAULT_PORT),
        "message": (
            f"Set {env_var}={env_value}. "
            "App restart initiated. Run command again in a few seconds."
        ),
    }


def _set_user_env_var(name: str, value: str) -> None:
    import ctypes
    import winreg

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_SET_VALUE
    )
    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
    winreg.CloseKey(key)
    ctypes.windll.user32.SendMessageTimeoutW(
        0xFFFF, 0x001A, 0, "Environment", 0, 5000, None
    )


def _find_app_pids(app_name: str) -> list[int]:
    result = subprocess.run(
        ["tasklist", "/fo", "csv", "/nh"],
        capture_output=True,
        text=True,
    )
    pids: list[int] = []
    needle = app_name.lower()
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.strip('"').split('","')
        if len(parts) >= 2:
            try:
                pid = int(parts[1])
            except ValueError:
                continue
            if needle in parts[0].lower():
                pids.append(pid)
    return pids


def _find_app_exe(app_name: str) -> str | None:
    return None


def _ensure_windows() -> None:
    if not is_windows():
        raise RuntimeError("CDP WebView2 support is only available on Windows")
