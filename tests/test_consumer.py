from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from app_automate.consumer import Consumer

FIREFOX_PATH = Path("examples/profiles/firefox/profile.json")
CHROME_PATH = Path("examples/profiles/chrome/profile.json")


def _mock_adapter():
    return MagicMock()


def test_from_file() -> None:
    c = Consumer.from_file(FIREFOX_PATH)
    assert c.profile_id == "firefox"
    assert c.app_name == "Firefox"


def test_from_directory() -> None:
    c = Consumer.from_file(Path("examples/profiles/firefox"))
    assert c.profile_id == "firefox"


def test_from_dict() -> None:
    data = json.loads(FIREFOX_PATH.read_text())
    c = Consumer.from_dict(data)
    assert c.profile_id == "firefox"


def test_resolve_by_label() -> None:
    c = Consumer.from_file(FIREFOX_PATH)
    el = c.resolve("url_bar")
    assert el.action.value == "shortcut"
    assert el.shortcut is not None
    assert el.shortcut.keys == "ctrl+l"


def test_resolve_by_alias() -> None:
    c = Consumer.from_file(FIREFOX_PATH)
    el = c.resolve("address bar")
    assert el.shortcut is not None


def test_resolve_by_element_id() -> None:
    c = Consumer.from_file(FIREFOX_PATH)
    el = c.resolve("url_bar_shortcut")
    assert el.shortcut is not None


def test_resolve_case_insensitive() -> None:
    c = Consumer.from_file(FIREFOX_PATH)
    el = c.resolve("URL_BAR")
    assert el.shortcut is not None


def test_resolve_not_found() -> None:
    c = Consumer.from_file(FIREFOX_PATH)
    try:
        c.resolve("does not exist")
        assert False, "should have raised KeyError"
    except KeyError as exc:
        assert "does not exist" in str(exc)
        assert "Available:" in str(exc)


def test_resolve_id() -> None:
    c = Consumer.from_file(FIREFOX_PATH)
    assert c.resolve_id("new tab") == "new_tab_shortcut"


def test_list_commands() -> None:
    c = Consumer.from_file(FIREFOX_PATH)
    cmds = c.list_commands()
    assert "new_tab" in cmds
    assert "open tab" in cmds
    assert "new tab" in cmds


def test_list_elements() -> None:
    c = Consumer.from_file(FIREFOX_PATH)
    els = c.list_elements()
    assert "url_bar_shortcut" in els
    assert "new_tab_shortcut" in els


def test_list_shortcuts() -> None:
    c = Consumer.from_file(FIREFOX_PATH)
    shortcuts = c.list_shortcuts()
    assert shortcuts["new_tab"] == "ctrl+t"
    assert shortcuts["quit"] == "ctrl+q"


def test_execute_dry_run() -> None:
    c = Consumer.from_file(FIREFOX_PATH)
    result = c.execute("new tab", dry_run=True)
    assert result.action == "shortcut"
    assert result.label == "new_tab"
    assert result.element_id == "new_tab_shortcut"


def test_execute_shortcut() -> None:
    adapter = _mock_adapter()
    c = Consumer.from_file(FIREFOX_PATH, adapter=adapter)
    result = c.execute("new tab")
    adapter.hotkey.assert_called_once_with("ctrl", "t")
    assert result.action == "shortcut"


def test_execute_type_requires_text() -> None:
    with TemporaryDirectory() as tmp:
        p = Path(tmp) / "profile.json"
        profile_data = json.loads(CHROME_PATH.read_text())
        profile_data["semantic_elements"]["test_type"] = {
            "label": "test type",
            "action": "type",
        }
        p.write_text(json.dumps(profile_data))
        c2 = Consumer.from_file(p)
        try:
            c2.execute("test type")
            assert False, "should have raised ValueError"
        except ValueError as exc:
            assert "requires text" in str(exc)


def test_chrome_profile_commands() -> None:
    c = Consumer.from_file(CHROME_PATH)
    cmds = c.list_commands()
    assert "address bar" in cmds
    assert "url" in cmds
    assert "new tab" in cmds


def test_cross_profile_resolve() -> None:
    for path in [
        "examples/profiles/firefox",
        "examples/profiles/chrome",
        "examples/profiles/vscode",
        "examples/profiles/libreoffice-writer",
    ]:
        c = Consumer.from_file(Path(path))
        cmds = c.list_commands()
        assert len(cmds) > 0, f"{path} has no commands"
