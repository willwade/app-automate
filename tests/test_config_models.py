from __future__ import annotations

from pathlib import Path

from app_automate.config.validation import load_profile


def test_example_profile_loads() -> None:
    profile = load_profile(Path("examples/profiles/camera-demo/profile.json"))
    assert profile.profile_id == "camera-demo"
    assert "shutter_btn" in profile.elements


def test_photo_booth_profile_loads() -> None:
    profile = load_profile(Path("examples/profiles/photo-booth/profile.json"))
    assert profile.profile_id == "photo-booth"
    assert "effects_btn" in profile.elements


def test_shortcut_definition_platform_keys() -> None:
    from app_automate.config.models import ShortcutDefinition

    sd = ShortcutDefinition(keys="ctrl+t", keys_macos="cmd+t")
    assert sd.keys_for_platform("darwin") == "cmd+t"
    assert sd.keys_for_platform("linux") == "ctrl+t"
    assert sd.keys_for_platform("windows") == "ctrl+t"

    sd_no_mac = ShortcutDefinition(keys="ctrl+s")
    assert sd_no_mac.keys_for_platform("darwin") == "ctrl+s"
