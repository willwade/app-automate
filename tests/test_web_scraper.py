from __future__ import annotations

from app_automate.shortcuts.web_scraper import (
    scrape_shortcuts_from_url,
)


class FakeFetcher:
    def __init__(self, html: str) -> None:
        self.html = html
        self.urls_fetched: list[str] = []

    def fetch(self, url: str) -> str:
        self.urls_fetched.append(url)
        return self.html


def test_scrape_table_with_headers() -> None:
    html = """
    <html><body>
    <table>
      <tr><th>Action</th><th>Shortcut</th></tr>
      <tr><td>Save</td><td>Ctrl+S</td></tr>
      <tr><td>Open</td><td>Ctrl+O</td></tr>
      <tr><td>Quit</td><td>Ctrl+Q</td></tr>
    </table>
    </body></html>
    """
    result = scrape_shortcuts_from_url(
        "https://example.com/shortcuts",
        "TestApp",
        fetcher=FakeFetcher(html),
    )
    assert len(result.shortcuts) == 3
    assert result.shortcuts[0].action == "save"
    assert result.shortcuts[0].keys == "ctrl+S"
    assert result.shortcuts[0].description == "Save"


def test_scrape_table_without_headers() -> None:
    html = """
    <html><body>
    <table>
      <tr><td>Copy</td><td>Ctrl+C</td></tr>
      <tr><td>Paste</td><td>Ctrl+V</td></tr>
    </table>
    </body></html>
    """
    result = scrape_shortcuts_from_url(
        "https://example.com/shortcuts",
        "TestApp",
        fetcher=FakeFetcher(html),
    )
    assert len(result.shortcuts) == 2
    assert result.shortcuts[0].action == "copy"


def test_scrape_definition_list() -> None:
    html = """
    <html><body>
    <dl>
      <dt>Undo</dt><dd>Ctrl+Z</dd>
      <dt>Redo</dt><dd>Ctrl+Shift+Z</dd>
    </dl>
    </body></html>
    """
    result = scrape_shortcuts_from_url(
        "https://example.com/shortcuts",
        "TestApp",
        fetcher=FakeFetcher(html),
    )
    assert len(result.shortcuts) == 2
    assert result.shortcuts[0].action == "undo"
    assert result.shortcuts[1].keys == "ctrl+shift+Z"


def test_scrape_fetch_failure() -> None:
    class FailFetcher:
        def fetch(self, url: str) -> str:
            raise ConnectionError("no network")

    result = scrape_shortcuts_from_url(
        "https://example.com/shortcuts",
        "TestApp",
        fetcher=FailFetcher(),
    )
    assert len(result.shortcuts) == 0
    assert len(result.warnings) == 1
    assert "fetch failed" in result.warnings[0]


def test_scrape_normalises_symbols() -> None:
    html = """
    <html><body>
    <table>
      <tr><th>Action</th><th>Key</th></tr>
      <tr><td>Save</td><td>⌘S</td></tr>
      <tr><td>Close</td><td>⌘W</td></tr>
    </table>
    </body></html>
    """
    result = scrape_shortcuts_from_url(
        "https://example.com/shortcuts",
        "TestApp",
        fetcher=FakeFetcher(html),
    )
    assert result.shortcuts[0].keys == "cmd+S"
    assert result.shortcuts[1].keys == "cmd+W"


def test_scrape_handles_multiple_keys() -> None:
    html = """
    <html><body>
    <table>
      <tr><th>Action</th><th>Keyboard Shortcut</th></tr>
      <tr><td>Zoom In</td><td>Ctrl + Plus</td></tr>
    </table>
    </body></html>
    """
    result = scrape_shortcuts_from_url(
        "https://example.com/shortcuts",
        "TestApp",
        fetcher=FakeFetcher(html),
    )
    assert len(result.shortcuts) == 1
    assert "Plus" in result.shortcuts[0].keys


def test_scrape_empty_page() -> None:
    result = scrape_shortcuts_from_url(
        "https://example.com/shortcuts",
        "TestApp",
        fetcher=FakeFetcher("<html><body><p>No shortcuts here</p></body></html>"),
    )
    assert len(result.shortcuts) == 0


def test_scrape_takes_first_of_alternatives() -> None:
    html = """
    <html><body>
    <table>
      <tr><th>Action</th><th>Shortcut</th></tr>
      <tr><td>Save</td><td>Ctrl+S, Cmd+S</td></tr>
    </table>
    </body></html>
    """
    result = scrape_shortcuts_from_url(
        "https://example.com/shortcuts",
        "TestApp",
        fetcher=FakeFetcher(html),
    )
    assert len(result.shortcuts) == 1
    assert result.shortcuts[0].keys == "ctrl+S"


def test_scrape_text_patterns_fallback() -> None:
    html = """
    <html><body>
    <div>
      <p>Copy selection - Ctrl+C</p>
      <p>Paste content - Ctrl+V</p>
      <p>Undo action - Ctrl+Z</p>
      <p>This is just a paragraph with no shortcuts</p>
    </div>
    </body></html>
    """
    result = scrape_shortcuts_from_url(
        "https://example.com/shortcuts",
        "TestApp",
        fetcher=FakeFetcher(html),
    )
    assert len(result.shortcuts) == 3
    assert result.shortcuts[0].keys == "ctrl+C"
    assert result.shortcuts[1].action == "paste_content"


def test_scrape_text_patterns_with_dashes() -> None:
    html = """
    <html><body>
    <div>
      <p>Bold text — Ctrl+B</p>
      <p>Italic text – Ctrl+I</p>
    </div>
    </body></html>
    """
    result = scrape_shortcuts_from_url(
        "https://example.com/shortcuts",
        "TestApp",
        fetcher=FakeFetcher(html),
    )
    assert len(result.shortcuts) == 2


def test_scrape_text_patterns_deduplicates() -> None:
    html = """
    <html><body>
    <div>
      <p>Save - Ctrl+S</p>
      <p>Save - Ctrl+S</p>
    </div>
    </body></html>
    """
    result = scrape_shortcuts_from_url(
        "https://example.com/shortcuts",
        "TestApp",
        fetcher=FakeFetcher(html),
    )
    assert len(result.shortcuts) == 1
