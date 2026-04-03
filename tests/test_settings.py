"""
settings.py — unit tests.

Tests load_settings() and save_settings(): defaults fallback, bool/int/string
coercion, comment skipping, round-trip persistence, and I/O failure handling.

FERPA: no real student data. I/O uses tmp_path + monkeypatch — never touches
~/.canvas_autograder_settings.

Run with: python3 -m pytest tests/test_settings.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import settings as settings_module
from settings import load_settings, save_settings, _DEFAULTS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_and_load(tmp_path, monkeypatch, content: str) -> dict:
    f = tmp_path / "settings.txt"
    f.write_text(content, encoding="utf-8")
    monkeypatch.setattr(settings_module, "SETTINGS_FILE", f)
    return load_settings()


# ---------------------------------------------------------------------------
# load_settings — no file (pure defaults)
# ---------------------------------------------------------------------------

class TestLoadSettingsNoFile:
    def test_returns_dict(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings_module, "SETTINGS_FILE", tmp_path / "nonexistent.txt")
        result = load_settings()
        assert isinstance(result, dict)

    def test_all_default_keys_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings_module, "SETTINGS_FILE", tmp_path / "nonexistent.txt")
        result = load_settings()
        for key in _DEFAULTS:
            assert key in result, f"Missing default key: {key}"

    def test_default_values_match(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings_module, "SETTINGS_FILE", tmp_path / "nonexistent.txt")
        result = load_settings()
        assert result["auto_open_folder"] is False
        assert result["default_min_words"] == 200
        assert result["font_scale"] == 1.25
        assert result["institution_type"] == "community_college"
        assert result["data_retention_enabled"] is True
        assert result["data_retention_days"] == 180

    def test_no_file_is_not_mutation_of_defaults(self, tmp_path, monkeypatch):
        """load_settings() must return a new dict, not the _DEFAULTS object."""
        monkeypatch.setattr(settings_module, "SETTINGS_FILE", tmp_path / "nonexistent.txt")
        result = load_settings()
        result["auto_open_folder"] = True
        assert _DEFAULTS["auto_open_folder"] is False


# ---------------------------------------------------------------------------
# load_settings — bool coercion
# ---------------------------------------------------------------------------

class TestLoadSettingsBoolCoercion:
    def test_true_string(self, tmp_path, monkeypatch):
        r = _write_and_load(tmp_path, monkeypatch, "auto_open_folder=true\n")
        assert r["auto_open_folder"] is True

    def test_false_string(self, tmp_path, monkeypatch):
        r = _write_and_load(tmp_path, monkeypatch, "auto_open_folder=false\n")
        assert r["auto_open_folder"] is False

    def test_one_string(self, tmp_path, monkeypatch):
        r = _write_and_load(tmp_path, monkeypatch, "auto_open_folder=1\n")
        assert r["auto_open_folder"] is True

    def test_zero_string(self, tmp_path, monkeypatch):
        r = _write_and_load(tmp_path, monkeypatch, "auto_open_folder=0\n")
        assert r["auto_open_folder"] is False

    def test_yes_string(self, tmp_path, monkeypatch):
        r = _write_and_load(tmp_path, monkeypatch, "auto_open_folder=yes\n")
        assert r["auto_open_folder"] is True

    def test_no_string(self, tmp_path, monkeypatch):
        r = _write_and_load(tmp_path, monkeypatch, "auto_open_folder=no\n")
        assert r["auto_open_folder"] is False

    def test_case_insensitive_true(self, tmp_path, monkeypatch):
        r = _write_and_load(tmp_path, monkeypatch, "auto_open_folder=TRUE\n")
        assert r["auto_open_folder"] is True

    def test_case_insensitive_false(self, tmp_path, monkeypatch):
        r = _write_and_load(tmp_path, monkeypatch, "auto_open_folder=False\n")
        assert r["auto_open_folder"] is False

    def test_bool_takes_precedence_over_digit_for_zero(self, tmp_path, monkeypatch):
        """'0' matches the bool branch first — result is False, not int 0."""
        r = _write_and_load(tmp_path, monkeypatch, "auto_open_folder=0\n")
        assert r["auto_open_folder"] is False
        assert isinstance(r["auto_open_folder"], bool)


# ---------------------------------------------------------------------------
# load_settings — int coercion
# ---------------------------------------------------------------------------

class TestLoadSettingsIntCoercion:
    def test_digit_string_coerced_to_int(self, tmp_path, monkeypatch):
        r = _write_and_load(tmp_path, monkeypatch, "default_min_words=300\n")
        assert r["default_min_words"] == 300
        assert isinstance(r["default_min_words"], int)

    def test_multi_digit_int(self, tmp_path, monkeypatch):
        r = _write_and_load(tmp_path, monkeypatch, "cleanup_threshold_days=365\n")
        assert r["cleanup_threshold_days"] == 365
        assert isinstance(r["cleanup_threshold_days"], int)

    def test_float_string_passed_through_as_string(self, tmp_path, monkeypatch):
        """isdigit() fails for '1.25' — falls through to string."""
        r = _write_and_load(tmp_path, monkeypatch, "font_scale=1.5\n")
        assert r["font_scale"] == "1.5"


# ---------------------------------------------------------------------------
# load_settings — string passthrough and edge cases
# ---------------------------------------------------------------------------

class TestLoadSettingsStringAndEdgeCases:
    def test_string_value_preserved(self, tmp_path, monkeypatch):
        r = _write_and_load(tmp_path, monkeypatch, "institution_type=high_school\n")
        assert r["institution_type"] == "high_school"

    def test_comment_lines_skipped(self, tmp_path, monkeypatch):
        r = _write_and_load(tmp_path, monkeypatch,
            "# This is a comment\nauto_open_folder=true\n")
        assert r["auto_open_folder"] is True

    def test_blank_lines_skipped(self, tmp_path, monkeypatch):
        r = _write_and_load(tmp_path, monkeypatch,
            "\nauto_open_folder=true\n\n")
        assert r["auto_open_folder"] is True

    def test_missing_key_uses_default(self, tmp_path, monkeypatch):
        """File only has one key — rest fall back to defaults."""
        r = _write_and_load(tmp_path, monkeypatch, "auto_open_folder=true\n")
        assert r["default_min_words"] == 200

    def test_unknown_key_passed_through(self, tmp_path, monkeypatch):
        """Unknown keys survive (forward compat with future settings keys)."""
        r = _write_and_load(tmp_path, monkeypatch, "some_future_key=hello\n")
        assert r.get("some_future_key") == "hello"

    def test_equals_in_value_preserved(self, tmp_path, monkeypatch):
        """split('=', 1) means only first '=' is the separator."""
        r = _write_and_load(tmp_path, monkeypatch, "institution_type=a=b\n")
        assert r["institution_type"] == "a=b"

    def test_whitespace_around_key_value_stripped(self, tmp_path, monkeypatch):
        r = _write_and_load(tmp_path, monkeypatch, "  institution_type  =  high_school  \n")
        assert r["institution_type"] == "high_school"

    def test_line_without_equals_skipped(self, tmp_path, monkeypatch):
        """Lines without '=' are silently ignored."""
        r = _write_and_load(tmp_path, monkeypatch,
            "this line has no equals sign\nauto_open_folder=true\n")
        assert r["auto_open_folder"] is True

    def test_invalid_utf8_returns_defaults(self, tmp_path, monkeypatch):
        f = tmp_path / "bad.txt"
        f.write_bytes(b"\xff\xff\xff\xff")  # Not valid UTF-8
        monkeypatch.setattr(settings_module, "SETTINGS_FILE", f)
        result = load_settings()
        assert isinstance(result, dict)
        for key in _DEFAULTS:
            assert key in result


# ---------------------------------------------------------------------------
# save_settings
# ---------------------------------------------------------------------------

class TestSaveSettings:
    def test_returns_true_on_success(self, tmp_path, monkeypatch):
        f = tmp_path / "settings.txt"
        monkeypatch.setattr(settings_module, "SETTINGS_FILE", f)
        assert save_settings({"key": "value"}) is True

    def test_file_created(self, tmp_path, monkeypatch):
        f = tmp_path / "settings.txt"
        monkeypatch.setattr(settings_module, "SETTINGS_FILE", f)
        save_settings({"auto_open_folder": True})
        assert f.exists()

    def test_written_keys_present_in_file(self, tmp_path, monkeypatch):
        f = tmp_path / "settings.txt"
        monkeypatch.setattr(settings_module, "SETTINGS_FILE", f)
        save_settings({"auto_open_folder": True, "default_min_words": 300})
        content = f.read_text()
        assert "auto_open_folder=True" in content
        assert "default_min_words=300" in content

    def test_header_comment_written(self, tmp_path, monkeypatch):
        f = tmp_path / "settings.txt"
        monkeypatch.setattr(settings_module, "SETTINGS_FILE", f)
        save_settings({})
        assert "# Canvas Autograder Settings" in f.read_text()

    def test_empty_dict_saves_without_error(self, tmp_path, monkeypatch):
        f = tmp_path / "settings.txt"
        monkeypatch.setattr(settings_module, "SETTINGS_FILE", f)
        assert save_settings({}) is True

    def test_returns_false_on_unwritable_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings_module, "SETTINGS_FILE", tmp_path)
        result = save_settings({"key": "value"})
        assert result is False


# ---------------------------------------------------------------------------
# Round-trip: save → load
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_string_roundtrip(self, tmp_path, monkeypatch):
        f = tmp_path / "settings.txt"
        monkeypatch.setattr(settings_module, "SETTINGS_FILE", f)
        save_settings({"institution_type": "high_school"})
        r = load_settings()
        assert r["institution_type"] == "high_school"

    def test_bool_true_roundtrip(self, tmp_path, monkeypatch):
        f = tmp_path / "settings.txt"
        monkeypatch.setattr(settings_module, "SETTINGS_FILE", f)
        save_settings({"auto_open_folder": True})
        r = load_settings()
        # Saved as "True", loaded back through bool coercion → True
        assert r["auto_open_folder"] is True

    def test_int_roundtrip(self, tmp_path, monkeypatch):
        f = tmp_path / "settings.txt"
        monkeypatch.setattr(settings_module, "SETTINGS_FILE", f)
        save_settings({"default_min_words": 150})
        r = load_settings()
        assert r["default_min_words"] == 150

    def test_missing_saved_key_uses_default(self, tmp_path, monkeypatch):
        """Keys not in the saved file still come back with their defaults."""
        f = tmp_path / "settings.txt"
        monkeypatch.setattr(settings_module, "SETTINGS_FILE", f)
        save_settings({"institution_type": "high_school"})
        r = load_settings()
        assert r["default_min_words"] == 200
