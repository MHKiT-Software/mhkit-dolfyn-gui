"""Tests for userdata.json resolution and loading."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from mhkit_dolfyn_gui.models.file_item import FileItem
from mhkit_dolfyn_gui.services.userdata_service import load_userdata, resolve_userdata

if TYPE_CHECKING:
    from pathlib import Path


class TestLoadUserdata:
    def test_loads_valid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "userdata.json"
        p.write_text('{"inst_make": "Nortek"}')
        assert load_userdata(p) == {"inst_make": "Nortek"}

    def test_rejects_non_object(self, tmp_path: Path) -> None:
        p = tmp_path / "userdata.json"
        p.write_text("[1, 2, 3]")
        with pytest.raises(ValueError, match="must contain a JSON object"):
            load_userdata(p)

    def test_rejects_invalid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "userdata.json"
        p.write_text("{not: valid}")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_userdata(p)


class TestResolveUserdata:
    def test_skip_takes_precedence(self, tmp_path: Path) -> None:
        global_p = tmp_path / "global.userdata.json"
        global_p.write_text('{"a": 1}')
        item = FileItem(path=tmp_path / "file.ad2cp", userdata_skip=True)
        payload, source = resolve_userdata(item, global_p)
        assert payload is None
        assert source is None

    def test_sidecar_overrides_global(self, tmp_path: Path) -> None:
        input_path = tmp_path / "file.ad2cp"
        input_path.write_bytes(b"")
        sidecar = tmp_path / "file.userdata.json"
        sidecar.write_text('{"src": "sidecar"}')
        global_p = tmp_path / "global.userdata.json"
        global_p.write_text('{"src": "global"}')
        item = FileItem(path=input_path)
        payload, source = resolve_userdata(item, global_p)
        assert payload == {"src": "sidecar"}
        assert source == sidecar

    def test_falls_back_to_global(self, tmp_path: Path) -> None:
        input_path = tmp_path / "file.ad2cp"
        global_p = tmp_path / "global.userdata.json"
        global_p.write_text(json.dumps({"src": "global"}))
        item = FileItem(path=input_path)
        payload, source = resolve_userdata(item, global_p)
        assert payload == {"src": "global"}
        assert source == global_p

    def test_returns_none_when_nothing_set(self, tmp_path: Path) -> None:
        item = FileItem(path=tmp_path / "file.ad2cp")
        payload, source = resolve_userdata(item, None)
        assert payload is None
        assert source is None
