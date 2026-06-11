from __future__ import annotations

from app_automate.adapters.pyautogui_adapter import PyAutoGuiAdapter
from app_automate.platform_utils import is_macos


class MacOSActionAdapter(PyAutoGuiAdapter):
    def __init__(self) -> None:
        if not is_macos():
            raise RuntimeError("MacOSActionAdapter requires macOS")
