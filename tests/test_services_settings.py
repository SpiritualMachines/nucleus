"""Tests for the AppSetting get/set/initialize functions in core/services.py."""

from core import services


def test_get_setting_returns_default_when_key_missing():
    assert services.get_setting("nonexistent_key", "fallback") == "fallback"


def test_get_setting_returns_empty_string_default():
    assert services.get_setting("nonexistent_key") == ""


def test_set_and_get_setting():
    services.set_setting("test_key", "hello")
    assert services.get_setting("test_key") == "hello"


def test_set_setting_overwrites_existing_value():
    services.set_setting("version", "v1.0")
    services.set_setting("version", "v2.0")
    assert services.get_setting("version") == "v2.0"


def test_initialize_default_settings_seeds_missing_keys():
    services.initialize_default_settings({"hackspace_name": "TestSpace"})
    assert services.get_setting("hackspace_name") == "TestSpace"


def test_initialize_default_settings_does_not_overwrite_existing():
    services.set_setting("hackspace_name", "Original")
    services.initialize_default_settings({"hackspace_name": "ShouldNotOverwrite"})
    assert services.get_setting("hackspace_name") == "Original"


def test_initialize_default_settings_seeds_multiple_keys():
    services.initialize_default_settings(
        {
            "app_name": "Nucleus",
            "tag_name": "Makerspace",
        }
    )
    assert services.get_setting("app_name") == "Nucleus"
    assert services.get_setting("tag_name") == "Makerspace"
