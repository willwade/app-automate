from __future__ import annotations

from app_automate.config.key_validation import validate_key_string


def test_valid_single_key() -> None:
    assert validate_key_string("t") == []
    assert validate_key_string("enter") == []
    assert validate_key_string("f12") == []


def test_valid_modifier_combo() -> None:
    assert validate_key_string("ctrl+t") == []
    assert validate_key_string("ctrl+shift+s") == []
    assert validate_key_string("alt+left") == []
    assert validate_key_string("cmd+option+p") == []


def test_empty_keys() -> None:
    assert validate_key_string("") == ["empty key string"]
    assert validate_key_string("   ") == ["empty key string"]
    assert validate_key_string("++") == ["empty key string"]


def test_unknown_key() -> None:
    result = validate_key_string("ctrl+foobar")
    assert len(result) == 1
    assert "foobar" in result[0]


def test_platform_specific_macos() -> None:
    assert validate_key_string("cmd+t", platform="macos") == []
    assert validate_key_string("command+t", platform="macos") == []


def test_platform_specific_windows() -> None:
    assert validate_key_string("win+r", platform="windows") == []


def test_platform_specific_linux() -> None:
    assert validate_key_string("super+d", platform="linux") == []
    assert validate_key_string("meta+l", platform="linux") == []


def test_platform_key_wrong_platform() -> None:
    result = validate_key_string("super+d", platform="macos")
    assert result == []


def test_no_platform_super_is_unknown() -> None:
    result = validate_key_string("super+d")
    assert result == []


def test_f_key_range() -> None:
    assert validate_key_string("f1") == []
    assert validate_key_string("f12") == []
    assert validate_key_string("f24") == []


def test_plus_minus_equals() -> None:
    assert validate_key_string("plus") == []
    assert validate_key_string("minus") == []
    assert validate_key_string("equals") == []


def test_multi_unknown() -> None:
    result = validate_key_string("ctrl+foo+bar")
    assert len(result) == 2
