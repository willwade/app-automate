from __future__ import annotations

import pytest

from app_automate.accessibility.cdp import (
    CDPShortcut,
    _collect_shortcuts_from_page,
)


def _playwright_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
        return True
    except Exception:
        return False


needs_playwright = pytest.mark.skipif(
    not _playwright_available(),
    reason="Playwright chromium not installed",
)


@needs_playwright
def test_collect_aria_keyshortcuts() -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content("""
        <html><body>
        <button aria-keyshortcuts="Control+Shift+P"
                aria-label="Show Commands">Cmd</button>
        <button aria-keyshortcuts="Control+B" aria-label="Bold">B</button>
        <a href="/" accesskey="h" title="Home">Home</a>
        </body></html>
        """)
        page.wait_for_timeout(500)

        shortcuts: list[CDPShortcut] = []
        _collect_shortcuts_from_page(page, shortcuts)
        browser.close()

    aks = [s for s in shortcuts if s.source == "aria-keyshortcuts"]
    assert len(aks) == 2
    assert aks[0].keys == "Control+Shift+P"
    assert aks[0].label == "Show Commands"
    assert aks[1].keys == "Control+B"

    ax = [s for s in shortcuts if s.source == "ax-tree"]
    assert len(ax) >= 2
    ax_keys = {s.keys for s in ax}
    assert "Control+Shift+P" in ax_keys
    assert "Control+B" in ax_keys

    dom_ak = [s for s in shortcuts if s.source == "accesskey"]
    assert len(dom_ak) == 1
    assert dom_ak[0].keys == "h"


@needs_playwright
def test_collect_no_shortcuts() -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content("<html><body><button>No shortcuts</button></body></html>")
        page.wait_for_timeout(500)

        shortcuts: list[CDPShortcut] = []
        _collect_shortcuts_from_page(page, shortcuts)
        browser.close()

    assert len(shortcuts) == 0


def test_shortcut_as_dict() -> None:
    s = CDPShortcut(
        label="Bold", keys="Ctrl+B", role="button", source="aria-keyshortcuts"
    )
    d = s.as_dict()
    assert d["label"] == "Bold"
    assert d["keys"] == "Ctrl+B"
    assert d["source"] == "aria-keyshortcuts"
