from __future__ import annotations

import json
from pathlib import Path

from app_automate.shortcuts.extractors import (
    extract_from_desktop_file,
    extract_from_shortcuts_file,
)


def test_extract_from_json_shortcuts_file(tmp_path: Path) -> None:
    data = {
        "save": {"keys": "ctrl+s", "description": "Save file"},
        "quit": {"keys": "ctrl+q", "description": "Quit app"},
    }
    path = tmp_path / "shortcuts.json"
    path.write_text(json.dumps(data))

    results = extract_from_shortcuts_file(path)
    assert len(results) == 2
    assert results[0].action == "save"
    assert results[0].keys == "ctrl+s"
    assert results[0].source == f"file:{path.name}"
    assert results[1].action == "quit"


def test_extract_from_json_list_format(tmp_path: Path) -> None:
    data = [
        {"action": "copy", "keys": "ctrl+c", "description": "Copy"},
        {"action": "paste", "keys": "ctrl+v", "description": "Paste"},
    ]
    path = tmp_path / "shortcuts.json"
    path.write_text(json.dumps(data))

    results = extract_from_shortcuts_file(path)
    assert len(results) == 2
    assert results[0].action == "copy"
    assert results[0].keys == "ctrl+c"


def test_extract_from_text_shortcuts_equals(tmp_path: Path) -> None:
    content = "save = ctrl+s\nquit = ctrl q\n"
    path = tmp_path / "shortcuts.txt"
    path.write_text(content)

    results = extract_from_shortcuts_file(path)
    assert len(results) == 2
    assert results[0].action == "save"
    assert results[0].keys == "ctrl+s"


def test_extract_from_text_shortcuts_colon(tmp_path: Path) -> None:
    content = "save: ctrl+s\nquit: ctrl+q\n"
    path = tmp_path / "shortcuts.txt"
    path.write_text(content)

    results = extract_from_shortcuts_file(path)
    assert len(results) == 2
    assert results[0].action == "save"


def test_text_shortcuts_skips_comments_and_blanks(tmp_path: Path) -> None:
    content = "# comment\n\nsave = ctrl+s\n\n"
    path = tmp_path / "shortcuts.txt"
    path.write_text(content)

    results = extract_from_shortcuts_file(path)
    assert len(results) == 1
    assert results[0].action == "save"


def test_extract_from_missing_file(tmp_path: Path) -> None:
    results = extract_from_shortcuts_file(tmp_path / "nonexistent.json")
    assert results == []


def test_extract_from_desktop_file() -> None:
    results = extract_from_desktop_file("firefox")
    assert len(results) >= 1
    assert any("firefox" in r.action.lower() for r in results)


def test_extract_from_desktop_no_match() -> None:
    results = extract_from_desktop_file("nonexistent_app_xyz_12345")
    assert results == []


def test_to_definition(tmp_path: Path) -> None:
    data = {"save": {"keys": "ctrl+s", "description": "Save", "platform": "linux"}}
    path = tmp_path / "shortcuts.json"
    path.write_text(json.dumps(data))

    results = extract_from_shortcuts_file(path)
    definition = results[0].to_definition()
    assert definition.keys == "ctrl+s"
    assert definition.description == "Save"
    assert definition.platform == "linux"
