from __future__ import annotations

from app_automate.adapters.pyautogui_adapter import PyAutoGuiAdapter
from app_automate.platform_utils import is_linux


class LinuxInputAdapter(PyAutoGuiAdapter):
    """Linux input adapter. Falls back to PyAutoGUI for all actions."""

    def __init__(self) -> None:
        if not is_linux():
            raise RuntimeError("LinuxInputAdapter requires Linux")
