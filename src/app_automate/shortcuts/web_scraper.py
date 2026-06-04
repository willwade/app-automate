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


def _parse_table(table) -> list[TableShortcut]:
    shortcuts: list[TableShortcut] = []
    header_map: dict[int, str] = {}

    first_row = table.find("tr")
    if first_row is None:
        return shortcuts

    ths = first_row.find_all("th")
    if ths:
        for i, th in enumerate(ths):
            text = th.get_text(strip=True).lower()
            if any(k in text for k in ("shortcut", "key", "keyboard", " keystroke")):
                header_map["keys"] = i
            elif any(
                k in text for k in ("action", "command", "description", "feature")
            ):
                header_map["action"] = i

        if "keys" not in header_map or "action" not in header_map:
            return shortcuts

        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])
            action_idx = header_map["action"]
            keys_idx = header_map["keys"]
            if action_idx < len(cells) and keys_idx < len(cells):
                action = cells[action_idx].get_text(strip=True)
                keys = cells[keys_idx].get_text(strip=True)
                if action and keys:
                    shortcuts.append(TableShortcut(action=action, keys=keys))
    else:
        rows = table.find_all("tr")
        if len(rows) < 2:
            return shortcuts
        for row in rows:
            cells = row.find_all(["td", "th"])
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

    keys = (
        keys.replace("Ctrl+", "ctrl+")
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

    if not re.search(r"[a-zA-Z0-9]", keys):
        return ""

    return keys


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "_", slug)
    slug = slug.strip("_")
    return slug
