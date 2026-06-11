from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from app_automate.shortcuts.extractors import ExtractedShortcut


class UrlFetcher(Protocol):
    def fetch(self, url: str) -> str: ...


@dataclass
class TableShortcut:
    action: str
    keys: str


@dataclass
class ScraperResult:
    url: str
    app_name: str
    shortcuts: list[ExtractedShortcut] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class HttpxFetcher:
    def fetch(self, url: str) -> str:
        import httpx

        resp = httpx.get(url, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        return resp.text


class PlaywrightFetcher:
    def __init__(self, *, wait_seconds: float = 3.0) -> None:
        self.wait_seconds = wait_seconds

    def fetch(self, url: str) -> str:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(int(self.wait_seconds * 1000))
            html = page.content()
            browser.close()
            return html


def scrape_shortcuts_from_url(
    url: str,
    app_name: str,
    *,
    fetcher: UrlFetcher | None = None,
) -> ScraperResult:
    fetcher = fetcher or HttpxFetcher()
    result = ScraperResult(url=url, app_name=app_name)

    try:
        html = fetcher.fetch(url)
    except Exception as exc:
        result.warnings.append(f"fetch failed: {exc}")
        return result

    tables = _extract_tables(html)
    for table_shortcuts in tables:
        for ts in table_shortcuts:
            keys = _normalise_keys(ts.keys)
            if not keys:
                continue
            slug = _slugify(ts.action)
            result.shortcuts.append(
                ExtractedShortcut(
                    action=slug,
                    keys=keys,
                    source=f"web:{url}",
                    description=ts.action,
                )
            )

    if not result.shortcuts:
        result.shortcuts = _extract_from_text_patterns(html, url)
        if result.shortcuts:
            result.warnings.append(
                "extracted from text patterns (no tables found), review for accuracy"
            )

    return result


def _extract_tables(html: str) -> list[list[TableShortcut]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    results: list[list[TableShortcut]] = []

    for table in soup.find_all("table"):
        rows = _parse_table(table)
        if rows:
            results.append(rows)

    if not results:
        results.extend(_extract_from_definition_lists(soup))

    return results


def _is_section_header_row(th_list) -> bool:
    if len(th_list) != 1:
        return False
    th = th_list[0]
    colspan = th.get("colspan")
    if colspan and int(colspan) >= 2:
        return True
    return False


def _parse_table(table) -> list[TableShortcut]:
    shortcuts: list[TableShortcut] = []
    all_rows = table.find_all("tr")
    if not all_rows:
        return shortcuts

    first_row = all_rows[0]
    ths = first_row.find_all("th")

    if ths and not _is_section_header_row(ths):
        header_map: dict[str, int] = {}
        for i, th in enumerate(ths):
            text = th.get_text(strip=True).lower()
            if any(k in text for k in ("shortcut", "key", "keyboard", "keystroke")):
                header_map["keys"] = i
            elif any(
                k in text
                for k in (
                    "action",
                    "command",
                    "description",
                    "feature",
                    "effect",
                    "function",
                    "result",
                    "what it does",
                    "name",
                    "operation",
                )
            ):
                header_map["action"] = i

        if "keys" not in header_map or "action" not in header_map:
            return _parse_headerless_rows(all_rows)

        for row in all_rows[1:]:
            cells = row.find_all(["td", "th"])
            action_idx = header_map["action"]
            keys_idx = header_map["keys"]
            if action_idx < len(cells) and keys_idx < len(cells):
                action = cells[action_idx].get_text(strip=True)
                keys = cells[keys_idx].get_text(strip=True)
                if action and keys:
                    shortcuts.append(TableShortcut(action=action, keys=keys))
    else:
        shortcuts = _parse_headerless_rows(all_rows)

    return shortcuts


def _parse_headerless_rows(rows) -> list[TableShortcut]:
    shortcuts: list[TableShortcut] = []
    for row in rows:
        cells = row.find_all(["td", "th"])
        if len(cells) == 1:
            colspan = cells[0].get("colspan")
            if colspan and int(colspan) >= 2:
                continue
        if len(cells) >= 2:
            action = cells[0].get_text(strip=True)
            keys = cells[1].get_text(strip=True)
            if action and keys:
                shortcuts.append(TableShortcut(action=action, keys=keys))
    return shortcuts


def _extract_from_definition_lists(soup) -> list[list[TableShortcut]]:
    results: list[list[TableShortcut]] = []
    for dl in soup.find_all("dl"):
        shortcuts: list[TableShortcut] = []
        dts = dl.find_all("dt")
        for dt in dts:
            dd = dt.find_next_sibling("dd")
            if dd:
                action = dt.get_text(strip=True)
                keys = dd.get_text(strip=True)
                if action and keys:
                    shortcuts.append(TableShortcut(action=action, keys=keys))
        if shortcuts:
            results.append(shortcuts)
    return results


def _normalise_keys(raw: str) -> str:
    keys = raw.strip()
    if not keys:
        return ""

    keys = re.sub(r"\s*[,/]\s*", " or ", keys)
    keys = re.sub(r"\s+", " ", keys)

    if " or " in keys:
        keys = keys.split(" or ")[0].strip()

    keys = re.sub(r"CommandCtrl", "ctrl", keys, flags=re.I)
    keys = re.sub(r"OptionAlt", "alt", keys, flags=re.I)
    keys = re.sub(r"Option", "alt", keys, flags=re.I)

    keys = (
        keys.replace("Ctrl +", "ctrl+")
        .replace("Alt +", "alt+")
        .replace("Shift +", "shift+")
        .replace("Cmd +", "cmd+")
        .replace("Command +", "cmd+")
        .replace("Ctrl+", "ctrl+")
        .replace("Alt+", "alt+")
        .replace("Shift+", "shift+")
        .replace("Cmd+", "cmd+")
        .replace("Command+", "cmd+")
        .replace("⌘", "cmd+")
        .replace("⌃", "ctrl+")
        .replace("⌥", "alt+")
        .replace("⇧", "shift+")
    )

    keys = keys.replace(" + ", "+").replace(" - ", "-")

    keys = re.sub(r"(?<!\w)Enter(\s+key)?(?!\w)", "enter", keys, flags=re.I)
    keys = re.sub(r"(?<!\w)Esc(?!\w)", "escape", keys, flags=re.I)
    keys = re.sub(r"(?<!\w)Spacebar(?!\w)", "space", keys, flags=re.I)
    keys = re.sub(r"(?<!\w)Arrow\s+(keys|key)?(?!\w)", "", keys, flags=re.I)
    keys = re.sub(
        r"(?<!\w)(Up|Down|Left|Right)(?!\w)", lambda m: m.group(1).lower(), keys
    )

    keys = re.sub(r"\s+", "", keys)

    if not re.search(r"[a-zA-Z0-9]", keys):
        return ""

    return keys


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "_", slug)
    slug = slug.strip("_")
    return slug


_SHORTCUT_PATTERN = re.compile(
    r"(?P<action>.+?)\s*[–—\-:]\s*"
    r"(?P<keys>"
    r"(?:cmd|ctrl|alt|shift|⌘|⌃|⌥|⇧)"
    r"(?:\s*/\s*(?:cmd|ctrl|alt|shift|⌘|⌃|⌥|⇧))*"
    r"\s*\+?\s*[A-Za-z0-9\[\]←→↑↓]+"
    r"(?:\s*\+\s*[A-Za-z0-9\[\]←→↑↓]+)*"
    r")",
    re.I,
)


_STANDALONE_KEY_PATTERN = re.compile(
    r"^(?P<keys>"
    r"(?:cmd|ctrl|alt|shift|⌘|⌃|⌥|⇧)"
    r"(?:\s*/\s*(?:cmd|ctrl|alt|shift|⌘|⌃|⌥|⇧))*"
    r"\s*\+?\s*[A-Za-z0-9\[\]←→↑↓]+"
    r"(?:\s*(?:\+\s*|,\s*)[A-Za-z0-9\[\]←→↑↓]+)*"
    r")$",
    re.I,
)


def _extract_from_text_patterns(html: str, source_url: str) -> list[ExtractedShortcut]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.split("\n")]
    shortcuts: list[ExtractedShortcut] = []
    seen: set[str] = set()

    for i, line in enumerate(lines):
        if not line or len(line) > 300:
            continue

        for m in _SHORTCUT_PATTERN.finditer(line):
            action = m.group("action").strip()
            keys_raw = m.group("keys").strip()
            keys = _normalise_keys(keys_raw)
            if not keys:
                continue
            slug = _slugify(action)
            if not slug or slug in seen:
                continue
            seen.add(slug)
            shortcuts.append(
                ExtractedShortcut(
                    action=slug,
                    keys=keys,
                    source=f"web-text:{source_url}",
                    description=action,
                )
            )

    for i, line in enumerate(lines):
        if not line or len(line) > 100:
            continue
        m = _STANDALONE_KEY_PATTERN.match(line)
        if not m:
            continue
        keys_raw = m.group("keys").strip()
        keys = _normalise_keys(keys_raw)
        if not keys:
            continue
        action = ""
        for offset in range(1, max(i, len(lines) - i)):
            for j in (i - offset, i + offset):
                if 0 <= j < len(lines):
                    candidate = lines[j]
                    if (
                        candidate
                        and len(candidate) < 100
                        and not _STANDALONE_KEY_PATTERN.match(candidate)
                    ):
                        action = candidate
                        break
            if action:
                break
        if not action:
            continue
        slug = _slugify(action)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        shortcuts.append(
            ExtractedShortcut(
                action=slug,
                keys=keys,
                source=f"web-text-pair:{source_url}",
                description=action,
            )
        )

    return shortcuts
