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


def test_execute_click_action() -> None:
    adapter = _mock_adapter()
    with TemporaryDirectory() as tmp:
        p = Path(tmp) / "profile.json"
        p.write_text(
            json.dumps(
                {
                    "profile_id": "test",
                    "app_name": "Test",
                    "type": "semantic",
                    "backend": "mixed",
                    "semantic_elements": {
                        "btn": {"label": "click me", "action": "click"},
                    },
                }
            )
        )
        c = Consumer.from_file(p, adapter=adapter)
        result = c.execute("click me")
        adapter.click.assert_called_once_with(0, 0)
        assert result.action == "click"


def test_execute_double_click_action() -> None:
    adapter = _mock_adapter()
    with TemporaryDirectory() as tmp:
        p = Path(tmp) / "profile.json"
        p.write_text(
            json.dumps(
                {
                    "profile_id": "test",
                    "app_name": "Test",
                    "type": "semantic",
                    "backend": "mixed",
                    "semantic_elements": {
                        "btn": {"label": "dbl", "action": "double_click"},
                    },
                }
            )
        )
        c = Consumer.from_file(p, adapter=adapter)
        result = c.execute("dbl")
        adapter.double_click.assert_called_once_with(0, 0)
        assert result.action == "double_click"


def test_execute_right_click_action() -> None:
    adapter = _mock_adapter()
    with TemporaryDirectory() as tmp:
        p = Path(tmp) / "profile.json"
        p.write_text(
            json.dumps(
                {
                    "profile_id": "test",
                    "app_name": "Test",
                    "type": "semantic",
                    "backend": "mixed",
                    "semantic_elements": {
                        "btn": {"label": "righty", "action": "right_click"},
                    },
                }
            )
        )
        c = Consumer.from_file(p, adapter=adapter)
        c.execute("righty")
        adapter.right_click.assert_called_once_with(0, 0)


def test_execute_drag_action() -> None:
    adapter = _mock_adapter()
    with TemporaryDirectory() as tmp:
        p = Path(tmp) / "profile.json"
        p.write_text(
            json.dumps(
                {
                    "profile_id": "test",
                    "app_name": "Test",
                    "type": "semantic",
                    "backend": "mixed",
                    "semantic_elements": {
                        "slider": {
                            "label": "drag me",
                            "action": "drag",
                            "drag_dx": 100,
                            "drag_dy": -50,
                        },
                    },
                }
            )
        )
        c = Consumer.from_file(p, adapter=adapter)
        result = c.execute("drag me")
        adapter.drag.assert_called_once_with(0, 0, 100, -50)
        assert result.action == "drag"


def test_execute_scroll_action() -> None:
    adapter = _mock_adapter()
    with TemporaryDirectory() as tmp:
        p = Path(tmp) / "profile.json"
        p.write_text(
            json.dumps(
                {
                    "profile_id": "test",
                    "app_name": "Test",
                    "type": "semantic",
                    "backend": "mixed",
                    "semantic_elements": {
                        "area": {
                            "label": "scroll down",
                            "action": "scroll",
                            "scroll_clicks": 5,
                        },
                    },
                }
            )
        )
        c = Consumer.from_file(p, adapter=adapter)
        c.execute("scroll down")
        adapter.scroll.assert_called_once_with(0, 0, 5)


def test_execute_type_with_text() -> None:
    adapter = _mock_adapter()
    with TemporaryDirectory() as tmp:
        p = Path(tmp) / "profile.json"
        p.write_text(
            json.dumps(
                {
                    "profile_id": "test",
                    "app_name": "Test",
                    "type": "semantic",
                    "backend": "mixed",
                    "semantic_elements": {
                        "field": {
                            "label": "name",
                            "action": "type",
                            "text": "hello",
                        },
                    },
                }
            )
        )
        c = Consumer.from_file(p, adapter=adapter)
        result = c.execute("name")
        adapter.write_text.assert_called_once_with("hello")
        assert result.action == "type"


def test_execute_type_with_runtime_text() -> None:
    adapter = _mock_adapter()
    with TemporaryDirectory() as tmp:
        p = Path(tmp) / "profile.json"
        p.write_text(
            json.dumps(
                {
                    "profile_id": "test",
                    "app_name": "Test",
                    "type": "semantic",
                    "backend": "mixed",
                    "semantic_elements": {
                        "field": {
                            "label": "name",
                            "action": "type",
                            "text": "default",
                        },
                    },
                }
            )
        )
        c = Consumer.from_file(p, adapter=adapter)
        c.execute("name", text="override")
        adapter.write_text.assert_called_once_with("override")


def test_execute_wait_action() -> None:
    with TemporaryDirectory() as tmp:
        p = Path(tmp) / "profile.json"
        p.write_text(
            json.dumps(
                {
                    "profile_id": "test",
                    "app_name": "Test",
                    "type": "semantic",
                    "backend": "mixed",
                    "semantic_elements": {
                        "pause": {
                            "label": "wait",
                            "action": "wait",
                            "wait_ms": 10,
                        },
                    },
                }
            )
        )
        c = Consumer.from_file(p)
        import time

        start = time.monotonic()
        result = c.execute("wait")
        elapsed = time.monotonic() - start
        assert result.action == "wait"
        assert elapsed >= 0.01


def test_execute_hotkey_action() -> None:
    adapter = _mock_adapter()
    with TemporaryDirectory() as tmp:
        p = Path(tmp) / "profile.json"
        p.write_text(
            json.dumps(
                {
                    "profile_id": "test",
                    "app_name": "Test",
                    "type": "semantic",
                    "backend": "mixed",
                    "semantic_elements": {
                        "hk": {
                            "label": "hot",
                            "action": "hotkey",
                            "hotkey": "ctrl+shift+i",
                        },
                    },
                }
            )
        )
        c = Consumer.from_file(p, adapter=adapter)
        result = c.execute("hot")
        adapter.hotkey.assert_called_once_with("ctrl", "shift", "i")
        assert result.action == "hotkey"


def test_send_shortcut() -> None:
    adapter = _mock_adapter()
    c = Consumer.from_file(FIREFOX_PATH, adapter=adapter)
    c.send_shortcut("ctrl+t")
    adapter.hotkey.assert_called_once_with("ctrl", "t")


def test_type_text() -> None:
    adapter = _mock_adapter()
    c = Consumer.from_file(FIREFOX_PATH, adapter=adapter)
    c.type_text("hello world")
    adapter.write_text.assert_called_once_with("hello world")


def test_send_key() -> None:
    adapter = _mock_adapter()
    c = Consumer.from_file(FIREFOX_PATH, adapter=adapter)
    c.send_key("enter")
    adapter.hotkey.assert_called_once_with("enter")


def test_execute_unsupported_action() -> None:
    with TemporaryDirectory() as tmp:
        p = Path(tmp) / "profile.json"
        p.write_text(
            json.dumps(
                {
                    "profile_id": "test",
                    "app_name": "Test",
                    "type": "semantic",
                    "backend": "mixed",
                    "semantic_elements": {
                        "btn": {
                            "label": "ok",
                            "action": "click",
                        },
                    },
                }
            )
        )
        c = Consumer.from_file(p)
        result = c.execute("ok", dry_run=True)
        assert result.action == "click"
        assert result.element_id == "btn"
