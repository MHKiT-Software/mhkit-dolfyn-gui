"""Tests for summary template model and YAML persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from mhkit_dolfyn_gui.models.summary_template import (
    SummaryField,
    SummaryTemplate,
    get_default_combined_template,
    get_default_template,
    list_templates,
    load_template,
    save_template,
)


class TestSummaryField:
    def test_creation(self) -> None:
        f = SummaryField(path="attr.fs", label="Sampling Freq")
        assert f.path == "attr.fs"
        assert f.label == "Sampling Freq"


class TestSummaryTemplate:
    def test_roundtrip_dict(self) -> None:
        t = SummaryTemplate(
            name="Test",
            left=[SummaryField("attr.fs", "Freq")],
            right=[SummaryField("file.name", "File")],
        )
        d = t.to_dict()
        t2 = SummaryTemplate.from_dict(d)
        assert t2.name == "Test"
        assert len(t2.left) == 1
        assert t2.left[0].path == "attr.fs"
        assert len(t2.right) == 1
        assert t2.right[0].path == "file.name"
        assert t2.mode == "per_file"

    def test_roundtrip_dict_combined_mode(self) -> None:
        t = SummaryTemplate(
            name="Combined",
            left=[SummaryField("combined.files_loaded", "Files")],
            right=[],
            mode="combined",
        )
        d = t.to_dict()
        assert d["mode"] == "combined"
        t2 = SummaryTemplate.from_dict(d)
        assert t2.mode == "combined"
        assert t2.left[0].path == "combined.files_loaded"

    def test_from_dict_defaults(self) -> None:
        t = SummaryTemplate.from_dict({})
        assert t.name == "Untitled"
        assert t.left == []
        assert t.right == []
        assert t.mode == "per_file"


class TestYamlPersistence:
    def test_save_and_load(self, tmp_path: Path) -> None:
        t = SummaryTemplate(
            name="Custom",
            left=[SummaryField("attr.fs", "Freq"), SummaryField("dim.time", "Time Steps")],
            right=[SummaryField("file.name", "Filename")],
        )
        path = tmp_path / "custom.yaml"
        save_template(t, path)
        assert path.exists()

        loaded = load_template(path)
        assert loaded.name == "Custom"
        assert len(loaded.left) == 2
        assert loaded.left[0].path == "attr.fs"
        assert loaded.right[0].label == "Filename"

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "dir" / "template.yaml"
        t = SummaryTemplate(name="Nested")
        save_template(t, path)
        assert path.exists()


class TestDefaultTemplate:
    def test_loads_successfully(self) -> None:
        t = get_default_template()
        assert t.name == "Default"
        assert len(t.left) == 5
        assert len(t.right) == 5
        assert t.mode == "per_file"

    def test_left_column_paths(self) -> None:
        t = get_default_template()
        paths = [f.path for f in t.left]
        assert "computed.instrument" in paths
        assert "attr.serial_number" in paths

    def test_right_column_paths(self) -> None:
        t = get_default_template()
        paths = [f.path for f in t.right]
        assert "coord.time.first" in paths
        assert "file.name" in paths


class TestDefaultCombinedTemplate:
    def test_loads_successfully(self) -> None:
        t = get_default_combined_template()
        assert t.name == "Default Combined"
        assert t.mode == "combined"
        assert len(t.left) >= 1
        assert len(t.right) >= 1

    def test_has_combined_fields(self) -> None:
        t = get_default_combined_template()
        all_paths = [f.path for f in t.left + t.right]
        assert "combined.files_loaded" in all_paths
        assert "combined.total_ensembles" in all_paths


class TestListTemplates:
    def test_always_includes_default(self) -> None:
        templates = list_templates()
        assert len(templates) >= 1
        assert templates[0][0] == "Default"
        assert templates[0][1] is None

    def test_combined_mode_includes_combined_default(self) -> None:
        templates = list_templates(mode="combined")
        assert len(templates) >= 1
        assert templates[0][0] == "Default Combined"
        assert templates[0][1] is None

    def test_finds_user_templates(self, tmp_path: Path, monkeypatch) -> None:
        # Patch get_user_templates_dir to use tmp_path
        monkeypatch.setattr(
            "mhkit_dolfyn_gui.models.summary_template.get_user_templates_dir",
            lambda: tmp_path,
        )
        save_template(SummaryTemplate(name="UserCustom"), tmp_path / "custom.yaml")

        templates = list_templates()
        names = [t[0] for t in templates]
        assert "Default" in names
        assert "UserCustom" in names

    def test_mode_filter_excludes_other_modes(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "mhkit_dolfyn_gui.models.summary_template.get_user_templates_dir",
            lambda: tmp_path,
        )
        save_template(
            SummaryTemplate(name="MyCombined", mode="combined"),
            tmp_path / "combined.yaml",
        )
        save_template(
            SummaryTemplate(name="MyPerFile", mode="per_file"),
            tmp_path / "perfile.yaml",
        )

        per_file = list_templates(mode="per_file")
        names = [t[0] for t in per_file]
        assert "MyPerFile" in names
        assert "MyCombined" not in names

        combined = list_templates(mode="combined")
        names = [t[0] for t in combined]
        assert "MyCombined" in names
        assert "MyPerFile" not in names

    def test_skips_invalid_yaml(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "mhkit_dolfyn_gui.models.summary_template.get_user_templates_dir",
            lambda: tmp_path,
        )
        (tmp_path / "bad.yaml").write_text("not: [valid: yaml: {{")

        templates = list_templates()
        # Should still have Default, bad file skipped
        assert len(templates) >= 1
        assert templates[0][0] == "Default"
