from __future__ import annotations

from app_automate.adapters.pyautogui_adapter import PyAutoGuiAdapter
from app_automate.platform_utils import ensure_dpi_aware


class WindowsInputAdapter(PyAutoGuiAdapter):
    """Windows input adapter with DPI-aware coordinate handling."""

    def __init__(self) -> None:
        ensure_dpi_aware()
        super().__init__()
