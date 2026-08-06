"""Tests for export_pipeline — the single-source portable per-file body.

Two things are guarded here:

1. **Parity** — the source that :mod:`code_generator` embeds into generated
   scripts, when exec'd, behaves *identically* to the module the GUI runs. This
   is the drift guard: if the two ever diverge, this test fails.
2. **Behavior** — ``process_one_file`` selects the right profile, gates velds,
   passes userdata through, and creates the output directory.

Importing mhkit.dolfyn registers the ``ds.velds`` accessor used throughout.
"""

from __future__ import annotations

from pathlib import Path

import mhkit.dolfyn  # noqa: F401 — registers ds.velds accessor
import pytest
import xarray as xr

from mhkit_dolfyn_gui.services import export_pipeline
from mhkit_dolfyn_gui.services.code_generator import (
    ExportJobSpec,
    UserdataMode,
    _pipeline_source,
    generate_export_script,
)

_ROOT = Path(Path.cwd().anchor)


def _exec_embedded() -> dict:
    """Exec the embedded pipeline source in a fresh namespace and return it."""
    ns: dict = {}
    exec(compile(_pipeline_source(), "<embedded>", "exec"), ns)
    return ns


class TestEmbeddedSource:
    def test_no_gui_import_and_embed_safe(self) -> None:
        src = _pipeline_source()
        assert "import mhkit_dolfyn_gui" not in src
        assert "from mhkit_dolfyn_gui" not in src
        # A future import mid-script would be a SyntaxError once embedded.
        assert "from __future__" not in src

    def test_embedded_source_compiles_and_defines_api(self) -> None:
        ns = _exec_embedded()
        assert callable(ns["process_one_file"])
        assert callable(ns["inject_derived_velocity"])
        assert callable(ns["derived_velocity_pairs"])

    @pytest.mark.parametrize("coord_sys", ["earth", "inst", "beam", "principal"])
    def test_embedded_inject_matches_runtime(
        self, sample_adcp_dataset: xr.Dataset, coord_sys: str
    ) -> None:
        """The embedded inject and the imported inject produce identical output.

        Covers every coord system so any metadata (long_name/standard_name/
        comment) divergence between the two copies is caught.
        """
        ds = sample_adcp_dataset.copy()
        ds.attrs["coord_sys"] = coord_sys

        embedded_inject = _exec_embedded()["inject_derived_velocity"]
        expected = export_pipeline.inject_derived_velocity(ds)
        actual = embedded_inject(ds)

        xr.testing.assert_identical(actual, expected)


class TestProcessOneFile:
    def _stub_dolfyn(self, monkeypatch: pytest.MonkeyPatch, read_return):
        """Patch dolfyn.read/save on the real module; return a capture dict."""
        import mhkit.dolfyn as dolfyn

        captured: dict = {}

        def fake_read(path, **kwargs):
            captured["read"] = {"path": path, "kwargs": kwargs}
            return read_return

        def fake_save(ds, path):
            captured["saved"] = {"ds": ds, "path": path}

        monkeypatch.setattr(dolfyn, "read", fake_read)
        monkeypatch.setattr(dolfyn, "save", fake_save)
        return captured

    def test_selects_profile_from_tuple(
        self, monkeypatch: pytest.MonkeyPatch, sample_adcp_dataset: xr.Dataset, tmp_path
    ) -> None:
        ds0 = sample_adcp_dataset.assign_attrs(_profile="zero")
        ds1 = sample_adcp_dataset.assign_attrs(_profile="one")
        captured = self._stub_dolfyn(monkeypatch, (ds0, ds1))

        out = tmp_path / "nested" / "a.nc"
        result = export_pipeline.process_one_file(
            tmp_path / "a.vec", out, profile_index=1, include_velds=False
        )

        assert result == out
        assert out.parent.exists()  # mkdir(parents=True) happened
        assert captured["saved"]["ds"].attrs["_profile"] == "one"
        assert captured["saved"]["path"] == str(out)

    def test_single_dataset_passthrough(
        self, monkeypatch: pytest.MonkeyPatch, sample_adcp_dataset: xr.Dataset, tmp_path
    ) -> None:
        captured = self._stub_dolfyn(monkeypatch, sample_adcp_dataset)
        export_pipeline.process_one_file(
            tmp_path / "a.vec", tmp_path / "a.nc", include_velds=False
        )
        # include_velds=False -> no derived vars added
        assert "U_mag" not in captured["saved"]["ds"].data_vars

    def test_include_velds_injects(
        self, monkeypatch: pytest.MonkeyPatch, sample_adcp_dataset: xr.Dataset, tmp_path
    ) -> None:
        captured = self._stub_dolfyn(monkeypatch, sample_adcp_dataset)
        export_pipeline.process_one_file(
            tmp_path / "a.vec", tmp_path / "a.nc", include_velds=True
        )
        for name in export_pipeline.VELDS_PROP_NAMES:
            assert name in captured["saved"]["ds"].data_vars

    def test_userdata_passed_through(
        self, monkeypatch: pytest.MonkeyPatch, sample_adcp_dataset: xr.Dataset, tmp_path
    ) -> None:
        captured = self._stub_dolfyn(monkeypatch, sample_adcp_dataset)
        export_pipeline.process_one_file(
            tmp_path / "a.vec", tmp_path / "a.nc", userdata={"sensor": "adcp"}
        )
        assert captured["read"]["kwargs"] == {"userdata": {"sensor": "adcp"}}

    def test_no_userdata_omits_kwarg(
        self, monkeypatch: pytest.MonkeyPatch, sample_adcp_dataset: xr.Dataset, tmp_path
    ) -> None:
        captured = self._stub_dolfyn(monkeypatch, sample_adcp_dataset)
        export_pipeline.process_one_file(tmp_path / "a.vec", tmp_path / "a.nc")
        assert captured["read"]["kwargs"] == {}


class TestGeneratedScriptRuns:
    """Exec a full generated script end-to-end against a stubbed dolfyn."""

    def test_script_reads_selects_profile_and_saves(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        import mhkit.dolfyn as dolfyn

        # Distinct sentinels per source; the multi-profile file returns a tuple.
        single = object()
        profiles = (object(), object(), object())

        def fake_read(path, **kwargs):
            return profiles if path.endswith("multi.vec") else single

        saved: list[tuple[object, str]] = []
        monkeypatch.setattr(dolfyn, "read", fake_read)
        monkeypatch.setattr(dolfyn, "save", lambda ds, path: saved.append((ds, path)))

        out = tmp_path / "out"
        jobs = [
            ExportJobSpec(
                source=_ROOT / "in" / "a.vec",
                output=out / "a.nc",
                profile_index=0,
                is_multi_profile=False,
                userdata_mode=UserdataMode.NONE,
                include_velds=False,
            ),
            ExportJobSpec(
                source=_ROOT / "in" / "multi.vec",
                output=out / "multi.nc",
                profile_index=2,
                is_multi_profile=True,
                userdata_mode=UserdataMode.NONE,
                include_velds=False,
            ),
        ]
        script = generate_export_script(jobs)

        exec(compile(script, "<generated>", "exec"), {})

        # Both files saved; the multi-profile file saved its selected profile.
        saved_by_stem = {Path(p).stem: ds for ds, p in saved}
        assert saved_by_stem["a"] is single
        assert saved_by_stem["multi"] is profiles[2]
