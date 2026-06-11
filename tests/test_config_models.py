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


def test_shortcut_all_platforms() -> None:
    from app_automate.config.models import ShortcutDefinition

    sd = ShortcutDefinition(
        keys="ctrl+t",
        keys_macos="cmd+t",
        keys_linux="ctrl+t",
        keys_windows="ctrl+t",
    )
    assert sd.keys_for_platform("darwin") == "cmd+t"
    assert sd.keys_for_platform("linux") == "ctrl+t"
    assert sd.keys_for_platform("windows") == "ctrl+t"


def test_semantic_profile_requires_backend() -> None:
    import json
    from tempfile import TemporaryDirectory

    from app_automate.config.models import AppProfile

    with TemporaryDirectory() as tmp:
        p = Path(tmp) / "profile.json"
        p.write_text(
            json.dumps(
                {
                    "profile_id": "test",
                    "app_name": "Test",
                    "type": "semantic",
                    "semantic_elements": {"btn": {"label": "ok", "action": "click"}},
                }
            )
        )
        try:
            AppProfile.model_validate_json(p.read_text())
            assert False, "should have raised"
        except Exception:
            pass


def test_visual_profile_requires_elements_or_states() -> None:
    import json
    from tempfile import TemporaryDirectory

    from app_automate.config.models import AppProfile

    with TemporaryDirectory() as tmp:
        p = Path(tmp) / "profile.json"
        p.write_text(
            json.dumps(
                {
                    "profile_id": "test",
                    "app_name": "Test",
                    "type": "visual",
                }
            )
        )
        try:
            AppProfile.model_validate_json(p.read_text())
            assert False, "should have raised"
        except Exception:
            pass


def test_profile_get_state() -> None:
    from app_automate.config.models import AppProfile

    data = {
        "profile_id": "test",
        "app_name": "Test",
        "type": "visual",
        "states": {
            "default": {
                "id": "default",
                "anchors": {"primary": {"id": "p", "path": "a.png", "x": 0, "y": 0}},
                "elements": {},
            },
        },
    }
    profile = AppProfile.model_validate(data)
    assert profile.get_state("default") is not None
    assert profile.get_state("nonexistent") is None


def test_profile_get_active_state_with_matches() -> None:
    from app_automate.config.models import AppProfile

    data = {
        "profile_id": "test",
        "app_name": "Test",
        "type": "visual",
        "states": {
            "default": {
                "id": "default",
                "anchors": {"primary": {"id": "p", "path": "a.png", "x": 0, "y": 0}},
                "elements": {},
            },
            "other": {
                "id": "other",
                "anchors": {"primary": {"id": "p", "path": "b.png", "x": 0, "y": 0}},
                "elements": {},
            },
        },
    }
    profile = AppProfile.model_validate(data)
    active = profile.get_active_state({"default": True, "other": False})
    assert active is not None
    assert active.id == "default"


def test_profile_get_active_state_fallback() -> None:
    from app_automate.config.models import AppProfile

    data = {
        "profile_id": "test",
        "app_name": "Test",
        "type": "visual",
        "default_state": "default",
        "states": {
            "default": {
                "id": "default",
                "anchors": {"primary": {"id": "p", "path": "a.png", "x": 0, "y": 0}},
                "elements": {},
            },
        },
    }
    profile = AppProfile.model_validate(data)
    active = profile.get_active_state(None)
    assert active is not None
    assert active.id == "default"


def test_save_and_load_profile() -> None:
    from tempfile import TemporaryDirectory

    from app_automate.config.models import AppProfile
    from app_automate.config.validation import load_profile, save_profile

    data = {
        "profile_id": "round-trip",
        "app_name": "Test",
        "type": "semantic",
        "backend": "shortcut",
        "semantic_elements": {
            "save": {
                "label": "save",
                "action": "shortcut",
                "shortcut": {"keys": "ctrl+s", "keys_macos": "cmd+s"},
            },
        },
    }
    with TemporaryDirectory() as tmp:
        p = Path(tmp) / "sub" / "profile.json"
        profile = AppProfile.model_validate(data)
        save_profile(profile, p)
        assert p.exists()
        loaded = load_profile(p)
        assert loaded.profile_id == "round-trip"
        assert "save" in loaded.semantic_elements
