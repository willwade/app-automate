from __future__ import annotations

from pathlib import Path

from app_automate.config.models import AppProfile, SemanticElement, ShortcutDefinition
from app_automate.config.validation import save_profile
from app_automate.runner.runtime import dry_run_semantic_command


def _make_shortcut_profile(tmp_path: Path) -> AppProfile:
    elements = {
        "open": SemanticElement(
            label="open",
            aliases=["open file"],
            action="shortcut",
            shortcut=ShortcutDefinition(keys="ctrl+o", description="Open file"),
        ),
        "save": SemanticElement(
            label="save",
            aliases=["save file"],
            action="shortcut",
            shortcut=ShortcutDefinition(keys="ctrl+s", description="Save"),
        ),
    }
    profile = AppProfile(
        profile_id="test-shortcuts",
        app_name="TestApp",
        type="semantic",
        backend="shortcut",
        semantic_elements=elements,
    )
    path = tmp_path / "profile.json"
    save_profile(profile, path)
    return profile


def test_dry_run_shortcut_returns_no_coordinates(tmp_path: Path) -> None:
    profile = _make_shortcut_profile(tmp_path)
    result = dry_run_semantic_command("open", profile)
    assert result.action == "shortcut"
    assert result.backend == "shortcut"
    assert result.x is None
    assert result.y is None
    assert result.label == "open"


def test_dry_run_shortcut_uses_alias(tmp_path: Path) -> None:
    profile = _make_shortcut_profile(tmp_path)
    result = dry_run_semantic_command("save file", profile)
    assert result.element_id == "save"
    assert result.action == "shortcut"


def test_dry_run_shortcut_case_insensitive(tmp_path: Path) -> None:
    profile = _make_shortcut_profile(tmp_path)
    result = dry_run_semantic_command("Open", profile)
    assert result.element_id == "open"
