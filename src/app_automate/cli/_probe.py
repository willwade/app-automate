from __future__ import annotations

import json
from typing import Annotated, Any

import typer

from app_automate.cli._shared import (
    app,
    load_cdp_accessibility,
    load_windows_accessibility,
)


@app.command("whats-here")
def whats_here(
    radius: Annotated[
        int,
        typer.Option(
            "--radius",
            help="Half-width of the search box around the cursor in pixels.",
        ),
    ] = 96,
    backend: Annotated[
        str,
        typer.Option(
            "--backend",
            help="Backend to use: uia, ax, or cdp.",
        ),
    ] = "uia",
    app_name: Annotated[
        str | None,
        typer.Option(
            "--app",
            help="App to query (required for UIA). If omitted, queries all windows.",
        ),
    ] = None,
    port: Annotated[
        int,
        typer.Option("--port", help="CDP port."),
    ] = 9222,
) -> None:
    try:
        import pyautogui

        mx, my = pyautogui.position()
        print(f"Cursor at ({mx}, {my}), searching {radius * 2}x{radius * 2} box...")

        x1 = mx - radius
        y1 = my - radius
        x2 = mx + radius
        y2 = my + radius

        if backend == "uia":
            _whats_here_uia(app_name, x1, y1, x2, y2)
        elif backend == "ax":
            _whats_here_ax(app_name, x1, y1, x2, y2)
        elif backend == "cdp":
            _whats_here_cdp(port, x1, y1, x2, y2)
        else:
            print(f"Unknown backend: {backend}")
            raise typer.Exit(code=1)
    except Exception as exc:
        typer.echo(f"whats-here failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _foreground_app_name() -> str | None:
    from app_automate.platform_utils import is_windows

    if not is_windows():
        return None
    import ctypes

    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return None
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd) + 1
    buf = ctypes.create_unicode_buffer(length)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length)
    title = buf.value
    if not title:
        return None
    for sep in (" - ", " — "):
        if sep in title:
            title = title.split(sep)[-1].strip()
    return title


def _whats_here_uia(app_name: str | None, x1: int, y1: int, x2: int, y2: int) -> None:
    from app_automate.accessibility import windows_uia

    if app_name:
        elements = windows_uia.list_app_ui_elements(
            app_name, max_depth=15, actionable_only=False
        )
    else:
        app_name = _foreground_app_name()
        if app_name:
            print(f"  Foreground window: {app_name}")
        elements = windows_uia.list_app_ui_elements(
            app_name or "", max_depth=15, actionable_only=False
        )

    nearby = []
    for el in elements:
        if el.x is None or el.y is None:
            continue
        el_x1 = el.x
        el_y1 = el.y
        el_x2 = el.x + (el.width or 0)
        el_y2 = el.y + (el.height or 0)
        if el_x2 < x1 or el_x1 > x2 or el_y2 < y1 or el_y1 > y2:
            continue
        nearby.append(el)

    if not nearby:
        print("No UIA elements found near cursor.")
        return

    nearby.sort(key=lambda e: (e.width or 0) * (e.height or 0))

    print(f"\n{len(nearby)} elements found:\n")
    print(f"  {'Label':<30} {'Role':<20} {'X':>5} {'Y':>5} {'W':>5} {'H':>5}")
    print(f"  {'-' * 30} {'-' * 20} {'-' * 5} {'-' * 5} {'-' * 5} {'-' * 5}")
    for el in nearby:
        label = (el.label or "")[:30]
        role = (el.role or el.class_name or "")[:20]
        print(
            f"  {label:<30} {role:<20} "
            f"{el.x or 0:>5} {el.y or 0:>5} "
            f"{el.width or 0:>5} {el.height or 0:>5}"
        )


def _whats_here_cdp(port: int, x1: int, y1: int, x2: int, y2: int) -> None:
    from app_automate.accessibility import cdp

    elements = cdp.list_cdp_elements(port, actionable_only=False)

    nearby = []
    for el in elements:
        if el.x is None or el.y is None:
            continue
        el_x1 = el.x
        el_y1 = el.y
        el_x2 = el.x + (el.width or 0)
        el_y2 = el.y + (el.height or 0)
        if el_x2 < x1 or el_x1 > x2 or el_y2 < y1 or el_y1 > y2:
            continue
        nearby.append(el)

    if not nearby:
        print("No CDP elements found near cursor.")
        return

    nearby.sort(key=lambda e: (e.width or 0) * (e.height or 0))

    print(f"\n{len(nearby)} elements found:\n")
    print(f"  {'Label':<30} {'Role':<20} {'X':>5} {'Y':>5} {'W':>5} {'H':>5}")
    print(f"  {'-' * 30} {'-' * 20} {'-' * 5} {'-' * 5} {'-' * 5} {'-' * 5}")
    for el in nearby:
        label = (el.label or "")[:30]
        role = (el.role or "")[:20]
        print(
            f"  {label:<30} {role:<20} "
            f"{el.x or 0:>5} {el.y or 0:>5} "
            f"{el.width or 0:>5} {el.height or 0:>5}"
        )


@app.command("probe")
def probe(
    app_name: Annotated[
        str,
        typer.Argument(help="App name or window title to probe."),
    ],
) -> None:
    result = _probe_app(app_name)
    typer.echo(json.dumps(result, indent=2))


def _probe_app(app_name: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "app_name": app_name,
        "uia": None,
        "cdp": None,
        "atspi": None,
        "ax": None,
        "recommendation": None,
    }

    uia_elements = _probe_uia(app_name)
    result["uia"] = uia_elements

    cdp_info = _probe_cdp()
    result["cdp"] = cdp_info

    atspi_info = _probe_atspi(app_name)
    result["atspi"] = atspi_info

    ax_info = _probe_ax(app_name)
    result["ax"] = ax_info

    if (
        uia_elements["interactive_with_bounds"] >= 20
        and not uia_elements["title_bar_only"]
    ):
        result["recommendation"] = "uia"
        result["reason"] = (
            f"UIA found {uia_elements['interactive_with_bounds']} "
            "interactive elements with bounds"
        )
    elif ax_info["available"] and ax_info["interactive_with_bounds"] >= 10:
        result["recommendation"] = "ax"
        result["reason"] = (
            f"AX found {ax_info['interactive_with_bounds']} "
            "interactive elements with bounds"
        )
    elif cdp_info["available"]:
        result["recommendation"] = "cdp"
        result["reason"] = (
            f"CDP available (page: {cdp_info['page_title']}), "
            f"UIA only found {uia_elements['interactive_with_bounds']} elements"
        )
    elif atspi_info["available"] and atspi_info["interactive_with_bounds"] >= 10:
        result["recommendation"] = "atspi"
        result["reason"] = (
            f"AT-SPI found {atspi_info['interactive_with_bounds']} "
            "interactive elements with bounds"
        )
    else:
        result["recommendation"] = "cv"
        result["reason"] = (
            "UIA/CDP/AT-SPI/AX coverage is poor; use visual profile with train --app"
        )

    return result


def _probe_uia(app_name: str) -> dict[str, Any]:
    info: dict[str, Any] = {
        "available": False,
        "interactive_with_bounds": 0,
        "title_bar_only": False,
    }
    try:
        wa = load_windows_accessibility()
        elements = wa.list_app_ui_elements(app_name, max_depth=15, actionable_only=True)
        with_bounds = [e for e in elements if e.has_bounds]
        info["available"] = True
        info["interactive_with_bounds"] = len(with_bounds)
        info["total_elements"] = len(elements)
        roles = set(e.class_name for e in with_bounds)
        info["roles"] = sorted(roles)
        title_roles = {
            "MenuBarControl",
            "MenuItemControl",
            "TitleBarControl",
        }
        if with_bounds:
            window_top = min(e.y for e in with_bounds if e.y is not None)
            window_heights = [(e.y or 0) + (e.height or 0) for e in with_bounds]
            window_bottom = max(window_heights) if window_heights else window_top + 50
            title_bar_threshold = window_top + (window_bottom - window_top) * 0.08
            below_title = [
                e
                for e in with_bounds
                if (e.y or 0) > title_bar_threshold or e.class_name not in title_roles
            ]
            if not below_title:
                info["title_bar_only"] = True
    except Exception:
        info["available"] = False
        info["error"] = "no matching window found or UIA unavailable"
    return info


def _probe_cdp() -> dict[str, Any]:
    info: dict[str, Any] = {
        "available": False,
        "port": 9222,
    }
    try:
        cdp = load_cdp_accessibility()
        status = cdp.cdp_status()
        if status.get("listening") == "true":
            info["available"] = True
            info["page_title"] = status.get("page_title", "")
            info["page_url"] = status.get("page_url", "")
    except Exception:
        info["available"] = False
    return info


def _probe_atspi(app_name: str) -> dict[str, Any]:
    info: dict[str, Any] = {
        "available": False,
        "interactive_with_bounds": 0,
    }
    try:
        from app_automate.accessibility import linux_atspi

        elements = linux_atspi.list_app_ui_elements(
            app_name, max_depth=10, actionable_only=True
        )
        with_bounds = [e for e in elements if e.has_bounds]
        info["available"] = True
        info["interactive_with_bounds"] = len(with_bounds)
        info["total_elements"] = len(elements)
        roles = set(e.class_name for e in with_bounds)
        info["roles"] = sorted(roles)
    except Exception:
        info["available"] = False
        info["error"] = "AT-SPI unavailable or app not found"
    return info


def _probe_ax(app_name: str) -> dict[str, Any]:
    info: dict[str, Any] = {
        "available": False,
        "interactive_with_bounds": 0,
    }
    try:
        from app_automate.accessibility.macos_ax import list_app_ui_elements

        elements = list_app_ui_elements(app_name, max_depth=10, actionable_only=True)
        with_bounds = [e for e in elements if e.has_bounds]
        info["available"] = True
        info["interactive_with_bounds"] = len(with_bounds)
        info["total_elements"] = len(elements)
        roles = set(
            e.role or e.class_name for e in with_bounds if e.role or e.class_name
        )
        info["roles"] = sorted(roles)
    except Exception:
        info["available"] = False
        info["error"] = "AX unavailable or app not found"
    return info


def _whats_here_ax(app_name: str | None, x1: int, y1: int, x2: int, y2: int) -> None:
    from app_automate.accessibility.macos_ax import list_app_ui_elements

    if not app_name:
        app_name = _macos_foreground_app()

    if app_name:
        print(f"  Foreground app: {app_name}")

    elements = list_app_ui_elements(app_name or "", max_depth=15, actionable_only=False)

    nearby = []
    for el in elements:
        if el.x is None or el.y is None:
            continue
        el_x1 = el.x
        el_y1 = el.y
        el_x2 = el.x + (el.width or 0)
        el_y2 = el.y + (el.height or 0)
        if el_x2 < x1 or el_x1 > x2 or el_y2 < y1 or el_y1 > y2:
            continue
        nearby.append(el)

    if not nearby:
        print("No AX elements found near cursor.")
        return

    nearby.sort(key=lambda e: (e.width or 0) * (e.height or 0))

    print(f"\n{len(nearby)} elements found:\n")
    print(f"  {'Label':<30} {'Role':<20} {'X':>5} {'Y':>5} {'W':>5} {'H':>5}")
    print(f"  {'-' * 30} {'-' * 20} {'-' * 5} {'-' * 5} {'-' * 5} {'-' * 5}")
    for el in nearby:
        label = (el.label or "")[:30]
        role = (el.role or el.class_name or "")[:20]
        print(
            f"  {label:<30} {role:<20} "
            f"{el.x or 0:>5} {el.y or 0:>5} "
            f"{el.width or 0:>5} {el.height or 0:>5}"
        )


def _macos_foreground_app() -> str | None:
    try:
        import subprocess

        result = subprocess.run(
            [
                "osascript",
                "-e",
                (
                    'tell application "System Events" to get name '
                    "of first process whose frontmost is true"
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None
