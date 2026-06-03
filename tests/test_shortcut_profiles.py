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
