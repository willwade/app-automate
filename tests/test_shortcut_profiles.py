from __future__ import annotations

from pathlib import Path

from app_automate.config.models import ActionType, ShortcutDefinition
from app_automate.config.validation import load_profile


def test_firefox_profile_loads() -> None:
    profile = load_profile(Path("examples/profiles/firefox/profile.json"))
    assert profile.profile_id == "firefox"
    assert profile.type == "semantic"
    assert profile.backend == "atspi"
    assert "url_bar_shortcut" in profile.semantic_elements
    assert len(profile.shortcuts) >= 16


def test_galculator_profile_loads() -> None:
    profile = load_profile(Path("examples/profiles/galculator/profile.json"))
    assert profile.profile_id == "galculator"
    assert "digit_1" in profile.semantic_elements
    assert "equals" in profile.semantic_elements


def test_shortcut_action_type_exists() -> None:
    assert ActionType.SHORTCUT.value == "shortcut"


def test_shortcut_definition_model() -> None:
    sd = ShortcutDefinition(keys="ctrl+l", description="Focus URL bar")
    assert sd.keys == "ctrl+l"
    assert sd.platform is None

    sd2 = ShortcutDefinition(keys="ctrl+t", description="New tab", platform="linux")
    assert sd2.platform == "linux"


def test_semantic_element_with_shortcut() -> None:
    profile = load_profile(Path("examples/profiles/firefox/profile.json"))
    el = profile.semantic_elements["url_bar_shortcut"]
    assert el.action == ActionType.SHORTCUT
    assert el.shortcut is not None
    assert el.shortcut.keys == "ctrl+l"
    assert el.aliases == ["address bar", "url", "location bar", "navigate"]


def test_semantic_element_without_shortcut() -> None:
    profile = load_profile(Path("examples/profiles/firefox/profile.json"))
    el = profile.semantic_elements["url_bar_atspi"]
    assert el.action == ActionType.TYPE
    assert el.shortcut is not None
    assert el.role == "entry"


def test_profile_shortcuts_dict() -> None:
    profile = load_profile(Path("examples/profiles/firefox/profile.json"))
    assert "new_tab" in profile.shortcuts
    assert profile.shortcuts["new_tab"].keys == "ctrl+t"
    assert profile.shortcuts["quit"].keys == "ctrl+q"


def test_galculator_all_digits_present() -> None:
    profile = load_profile(Path("examples/profiles/galculator/profile.json"))
    for digit in range(10):
        assert f"digit_{digit}" in profile.semantic_elements


def test_chrome_profile_loads() -> None:
    profile = load_profile(Path("examples/profiles/chrome/profile.json"))
    assert profile.profile_id == "chrome"
    assert profile.backend == "shortcut"
    assert profile.platform_hint is None
    assert "url_bar" in profile.semantic_elements
    assert "reopen_tab" in profile.shortcuts
    assert len(profile.shortcuts) >= 15


def test_chrome_shortcuts_file_valid() -> None:
    import json

    data = json.loads(
        Path("examples/profiles/chrome/chrome-shortcuts.json").read_text()
    )
    assert "new_tab" in data
    assert "view_source" in data
    assert data["url_bar"]["keys"] == "ctrl+l"


def test_vscode_profile_loads() -> None:
    profile = load_profile(Path("examples/profiles/vscode/profile.json"))
    assert profile.profile_id == "vscode"
    assert profile.backend == "shortcut"
    assert "command_palette" in profile.semantic_elements
    assert "toggle_terminal" in profile.shortcuts


def test_vscode_shortcuts_file_valid() -> None:
    import json

    data = json.loads(
        Path("examples/profiles/vscode/vscode-shortcuts.json").read_text()
    )
    assert "command_palette" in data
    assert "toggle_terminal" in data
    assert "delete_line" in data


def test_libreoffice_writer_profile_loads() -> None:
    profile = load_profile(Path("examples/profiles/libreoffice-writer/profile.json"))
    assert profile.profile_id == "libreoffice-writer"
    assert profile.backend == "shortcut"
    assert "bold" in profile.semantic_elements
    assert "spellcheck" in profile.semantic_elements
    assert "find_replace" in profile.shortcuts


def test_libreoffice_writer_shortcuts_file_valid() -> None:
    import json

    data = json.loads(
        Path(
            "examples/profiles/libreoffice-writer/libreoffice-writer-shortcuts.json"
        ).read_text()
    )
    assert "bold" in data
    assert "export_pdf" in data
    assert data["save"]["keys"] == "ctrl+s"


def test_all_profiles_have_quit() -> None:
    for name in ["firefox", "chrome", "vscode", "libreoffice-writer"]:
        profile = load_profile(Path(f"examples/profiles/{name}/profile.json"))
        assert "quit" in profile.shortcuts, f"{name} missing quit shortcut"
    for name in ["chrome", "vscode", "libreoffice-writer"]:
        profile = load_profile(Path(f"examples/profiles/{name}/profile.json"))
        assert "quit" in profile.semantic_elements, (
            f"{name} missing quit semantic element"
        )
    profile = load_profile(Path("examples/profiles/firefox/profile.json"))
    assert any(k.startswith("quit") for k in profile.semantic_elements), (
        "firefox missing quit semantic element"
    )
