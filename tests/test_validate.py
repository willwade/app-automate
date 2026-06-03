from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from typer.testing import CliRunner

from app_automate import cli

runner = CliRunner()


def test_validate_valid_profile() -> None:
    result = runner.invoke(
        cli.app,
        ["validate", "examples/profiles/firefox"],
    )
    assert result.exit_code == 0
    assert "OK" in result.stdout


def test_validate_shortcut_profile() -> None:
    result = runner.invoke(
        cli.app,
        ["validate", "examples/profiles/chrome"],
    )
    assert result.exit_code == 0
    assert "OK" in result.stdout


def test_validate_missing_file() -> None:
    result = runner.invoke(
        cli.app,
        ["validate", "examples/profiles/nonexistent"],
    )
    assert result.exit_code == 1


def test_validate_invalid_json() -> None:
    with TemporaryDirectory() as tmp:
        p = Path(tmp) / "profile.json"
        p.write_text("{bad json")
        result = runner.invoke(cli.app, ["validate", str(p)])
        assert result.exit_code == 1
        assert "FATAL" in result.stderr or "FATAL" in result.output


def test_validate_semantic_no_backend() -> None:
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
        result = runner.invoke(cli.app, ["validate", str(p)])
        assert result.exit_code != 0


def test_validate_shortcut_without_keys() -> None:
    with TemporaryDirectory() as tmp:
        p = Path(tmp) / "profile.json"
        p.write_text(
            json.dumps(
                {
                    "profile_id": "test",
                    "app_name": "Test",
                    "type": "semantic",
                    "backend": "shortcut",
                    "semantic_elements": {
                        "btn": {
                            "label": "ok",
                            "action": "shortcut",
                            "shortcut": {"keys": "ctrl+t"},
                        },
                    },
                    "shortcuts": {"empty": {"keys": ""}},
                }
            )
        )
        result = runner.invoke(cli.app, ["validate", str(p)])
        assert result.exit_code == 2
        assert "empty keys" in result.stderr or "empty keys" in result.output


def test_validate_all_example_profiles() -> None:
    profiles_dir = Path("examples/profiles")
    for profile_dir in sorted(profiles_dir.iterdir()):
        if not profile_dir.is_dir():
            continue
        profile_json = profile_dir / "profile.json"
        if not profile_json.exists():
            continue
        result = runner.invoke(cli.app, ["validate", str(profile_dir)])
        assert result.exit_code == 0, (
            f"validate failed for {profile_dir.name}: {result.output}"
        )
