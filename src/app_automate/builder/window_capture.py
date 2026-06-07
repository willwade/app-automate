from __future__ import annotations

import time
from pathlib import Path

from PIL import Image

from app_automate.platform_utils import (
    current_platform,
    ensure_dpi_aware,
    is_linux,
    is_macos,
    is_windows,
)


def capture_app_window(app_name: str, output_path: Path) -> Path:
    from app_automate.vision.screenshots import capture_main_display

    _activate_app(app_name)
    time.sleep(0.4)
    left, top, width, height = front_window_bounds(app_name)
    full_screen_path = output_path.parent / "screen.png"
    capture_main_display(full_screen_path)
    image = Image.open(full_screen_path)
    crop = image.crop((left, top, left + width, top + height))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    crop.save(output_path)
    return output_path


def front_window_bounds(app_name: str) -> tuple[int, int, int, int]:
    if is_macos():
        return _front_window_bounds_macos(app_name)
    if is_windows():
        return _front_window_bounds_windows(app_name)
    if is_linux():
        return _front_window_bounds_linux(app_name)
    raise RuntimeError(
        f"automatic app-window capture is not supported on {current_platform()}"
    )


def _activate_app(app_name: str) -> None:
    if is_macos():
        _activate_app_macos(app_name)
    elif is_windows():
        _activate_app_windows(app_name)
    elif is_linux():
        _activate_app_linux(app_name)
    else:
        raise RuntimeError(f"app activation is not supported on {current_platform()}")


# --- macOS -----------------------------------------------------------------


def _front_window_bounds_macos(app_name: str) -> tuple[int, int, int, int]:
    try:
        from app_automate.accessibility.macos_ax import _axtool, _has_axtool

        if _has_axtool():
            import json

            raw = _axtool("window-bounds", "--app", app_name, "--json")
            data = json.loads(raw)
            return data["x"], data["y"], data["width"], data["height"]
    except Exception:
        pass
    position_raw = _osascript(
        'tell application "System Events" to tell process '
        f'"{app_name}" to get position of front window'
    )
    size_raw = _osascript(
        'tell application "System Events" to tell process '
        f'"{app_name}" to get size of front window'
    )
    left, top = _parse_pair(position_raw)
    width, height = _parse_pair(size_raw)
    return left, top, width, height


def _activate_app_macos(app_name: str) -> None:
    _osascript(f'tell application "{app_name}" to activate')


def _osascript(script: str) -> str:
    import subprocess

    result = subprocess.run(
        ["osascript", "-e", script],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def _parse_pair(value: str) -> tuple[int, int]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        raise RuntimeError(f"unexpected window bounds response: {value}")
    return int(parts[0]), int(parts[1])


# --- Windows ---------------------------------------------------------------


def _front_window_bounds_windows(app_name: str) -> tuple[int, int, int, int]:
    ensure_dpi_aware()
    hwnds = _find_windows_by_title(app_name)
    if not hwnds:
        raise RuntimeError(f'no visible window found matching "{app_name}"')
    hwnd = hwnds[0]
    left, top, right, bottom = _get_window_rect(hwnd)
    return left, top, right - left, bottom - top


def activate_app(app_name: str) -> None:
    if is_windows():
        _activate_app_windows(app_name)
    elif is_linux():
        _activate_app_linux(app_name)
    else:
        import subprocess

        subprocess.run(
            ["osascript", "-e", f'tell application "{app_name}" to activate']
        )


def _activate_app_linux(app_name: str) -> None:
    import subprocess

    subprocess.run(["wmctrl", "-a", app_name], check=False, capture_output=True)


def _front_window_bounds_linux(app_name: str) -> tuple[int, int, int, int]:
    import subprocess

    result = subprocess.run(
        ["xdotool", "search", "--name", app_name],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f'no visible window found matching "{app_name}"')

    window_id = result.stdout.strip().split("\n")[0]
    geom = subprocess.run(
        ["xdotool", "getwindowgeometry", "--shell", window_id],
        capture_output=True,
        text=True,
    )
    geo = {}
    for line in geom.stdout.strip().split("\n"):
        if "=" in line:
            k, v = line.split("=", 1)
            geo[k.strip()] = int(v.strip())

    return geo.get("X", 0), geo.get("Y", 0), geo.get("WIDTH", 0), geo.get("HEIGHT", 0)


def _activate_app_windows(app_name: str) -> None:
    import ctypes

    ensure_dpi_aware()
    hwnds = _find_windows_by_title(app_name)
    if not hwnds:
        raise RuntimeError(f'no visible window found matching "{app_name}"')
    hwnd = hwnds[0]
    ctypes.windll.user32.ShowWindow(hwnd, 9)
    ctypes.windll.user32.SetForegroundWindow(hwnd)


def _find_windows_by_title(title: str) -> list:
    import ctypes
    import ctypes.wintypes

    matches: list = []

    @ctypes.WINFUNCTYPE(
        ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
    )
    def enum_callback(hwnd, _lparam):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                if title.lower() in buf.value.lower():
                    matches.append(hwnd)
        return True

    ctypes.windll.user32.EnumWindows(enum_callback, 0)
    return matches


def _get_window_rect(hwnd) -> tuple[int, int, int, int]:
    import ctypes
    import ctypes.wintypes

    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom
