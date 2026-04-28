"""Tests for the userdata editor's value parsing helpers."""

from __future__ import annotations

from mhkit_dolfyn_gui.widgets.userdata_editor import _format_value, _parse_value


class TestParseValue:
    def test_int(self) -> None:
        assert _parse_value("42") == 42

    def test_float(self) -> None:
        assert _parse_value("3.14") == 3.14

    def test_bool(self) -> None:
        assert _parse_value("true") is True

    def test_list(self) -> None:
        assert _parse_value("[1, 2, 3]") == [1, 2, 3]

    def test_string_fallback(self) -> None:
        assert _parse_value("Nortek") == "Nortek"

    def test_empty(self) -> None:
        assert _parse_value("") == ""


class TestFormatValue:
    def test_string(self) -> None:
        assert _format_value("Nortek") == "Nortek"

    def test_number(self) -> None:
        assert _format_value(3.14) == "3.14"

    def test_list(self) -> None:
        assert _format_value([1, 2, 3]) == "[1, 2, 3]"
