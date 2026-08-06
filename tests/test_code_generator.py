"""Tests for the pure export-script generator."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from mhkit_dolfyn_gui.services.code_generator import (
    ExportJobSpec,
    UserdataMode,
    generate_export_script,
)

FIXED = datetime(2026, 4, 7, 12, 0, 0)

# On Windows Path("/in/a.vec") is not absolute (no drive letter).
# Using the filesystem anchor (e.g. "C:\\" on Windows, "/" on POSIX) ensures
# paths are truly absolute on every platform.
_ROOT = Path(Path.cwd().anchor)


def _spec(**overrides: object) -> ExportJobSpec:
    """Build an ExportJobSpec with sensible defaults, overridable per-test."""
    defaults: dict[str, object] = {
        "source": _ROOT / "in" / "a.vec",
        "output": _ROOT / "out" / "a.nc",
        "profile_index": 0,
        "is_multi_profile": False,
        "userdata_mode": UserdataMode.NONE,
        "userdata_path": None,
    }
    defaults.update(overrides)
    return ExportJobSpec(**defaults)  # type: ignore[arg-type]


class TestExportJobSpec:
    def test_relative_source_rejected(self) -> None:
        with pytest.raises(ValueError, match="source path must be absolute"):
            ExportJobSpec(
                source=Path("relative/in.vec"),
                output=_ROOT / "out" / "a.nc",
                profile_index=0,
                is_multi_profile=False,
                userdata_mode=UserdataMode.NONE,
            )

    def test_relative_output_rejected(self) -> None:
        with pytest.raises(ValueError, match="output path must be absolute"):
            ExportJobSpec(
                source=_ROOT / "in" / "a.vec",
                output=Path("out/a.nc"),
                profile_index=0,
                is_multi_profile=False,
                userdata_mode=UserdataMode.NONE,
            )

    def test_explicit_requires_path(self) -> None:
        with pytest.raises(ValueError, match="userdata_path is required"):
            ExportJobSpec(
                source=_ROOT / "in" / "a.vec",
                output=_ROOT / "out" / "a.nc",
                profile_index=0,
                is_multi_profile=False,
                userdata_mode=UserdataMode.EXPLICIT,
                userdata_path=None,
            )

    def test_explicit_rejects_relative_userdata(self) -> None:
        with pytest.raises(ValueError, match="userdata path must be absolute"):
            ExportJobSpec(
                source=_ROOT / "in" / "a.vec",
                output=_ROOT / "out" / "a.nc",
                profile_index=0,
                is_multi_profile=False,
                userdata_mode=UserdataMode.EXPLICIT,
                userdata_path=Path("rel/global.json"),
            )


class TestGenerateExportScript:
    def test_header_contains_timestamp_and_imports(self) -> None:
        script = generate_export_script([_spec()], now=FIXED)
        assert "2026-04-07T12:00:00" in script
        assert "import mhkit.dolfyn as dolfyn" in script
        assert "from pathlib import Path" in script

    def test_emits_input_files_list(self) -> None:
        script = generate_export_script([_spec()], now=FIXED)
        assert "INPUT_FILES = [" in script
        assert "/in/a.vec" in script

    def test_emits_output_dir(self) -> None:
        script = generate_export_script([_spec()], now=FIXED)
        assert "OUTPUT_DIR = Path(" in script
        assert "/out" in script

    def test_none_userdata_omitted_from_dict(self) -> None:
        script = generate_export_script([_spec()], now=FIXED)
        assert "USERDATA" not in script
        # No userdata kwarg in the loop call when there are no overrides.
        assert "userdata=USERDATA.get(input_file)," not in script

    def test_auto_sidecar_omitted_from_dict(self) -> None:
        script = generate_export_script([_spec(userdata_mode=UserdataMode.AUTO)], now=FIXED)
        assert "USERDATA" not in script
        assert "userdata=USERDATA.get(input_file)," not in script

    def test_skip_emits_false_in_dict(self) -> None:
        script = generate_export_script([_spec(userdata_mode=UserdataMode.SKIP)], now=FIXED)
        assert "USERDATA = {" in script
        assert "False" in script
        assert "/in/a.vec" in script
        assert "userdata=USERDATA.get(input_file)," in script

    def test_explicit_emits_path_in_dict(self) -> None:
        script = generate_export_script(
            [
                _spec(
                    userdata_mode=UserdataMode.EXPLICIT,
                    userdata_path=_ROOT / "etc" / "global.json",
                )
            ],
            now=FIXED,
        )
        assert "USERDATA = {" in script
        assert "/in/a.vec" in script
        assert "/etc/global.json" in script
        assert "userdata=USERDATA.get(input_file)," in script

    def test_dict_mode_emits_inline_dict(self) -> None:
        script = generate_export_script(
            [_spec(userdata_mode=UserdataMode.DICT, userdata_dict={"key": "value", "n": 42})],
            now=FIXED,
        )
        assert "USERDATA = {" in script
        assert "/in/a.vec" in script
        assert "'key'" in script
        assert "'value'" in script
        assert "42" in script
        assert "userdata=USERDATA.get(input_file)," in script
        compile(script, "<generated>", "exec")

    def test_dict_mode_requires_userdata_dict(self) -> None:
        with pytest.raises(ValueError, match="userdata_dict is required"):
            ExportJobSpec(
                source=_ROOT / "in" / "a.vec",
                output=_ROOT / "out" / "a.nc",
                profile_index=0,
                is_multi_profile=False,
                userdata_mode=UserdataMode.DICT,
                userdata_dict=None,
            )

    def test_per_file_userdata_mixed_batch(self) -> None:
        """Each file's userdata setting is independent."""
        jobs = [
            _spec(source=_ROOT / "in" / "a.vec", output=_ROOT / "out" / "a.nc"),
            _spec(
                source=_ROOT / "in" / "b.vec",
                output=_ROOT / "out" / "b.nc",
                userdata_mode=UserdataMode.SKIP,
            ),
            _spec(
                source=_ROOT / "in" / "c.vec",
                output=_ROOT / "out" / "c.nc",
                userdata_mode=UserdataMode.EXPLICIT,
                userdata_path=_ROOT / "etc" / "global.json",
            ),
            _spec(
                source=_ROOT / "in" / "d.vec",
                output=_ROOT / "out" / "d.nc",
                userdata_mode=UserdataMode.DICT,
                userdata_dict={"sensor": "adcp"},
            ),
        ]
        script = generate_export_script(jobs, now=FIXED)
        # a.vec has no override — not in USERDATA dict
        userdata_block = script.split("USERDATA = {")[1].split("}")[0]
        assert "/in/a.vec" not in userdata_block
        # b.vec → False
        assert "/in/b.vec" in script
        assert "False" in script
        # c.vec → explicit path
        assert "/in/c.vec" in script
        assert "/etc/global.json" in script
        # d.vec → inline dict
        assert "/in/d.vec" in script
        assert "'sensor'" in script

    def test_loop_uses_userdata_get(self) -> None:
        script = generate_export_script([_spec(userdata_mode=UserdataMode.SKIP)], now=FIXED)
        assert "USERDATA.get(input_file)" in script
        assert "process_one_file(" in script

    def test_no_userdata_loop_omits_userdata_kwarg(self) -> None:
        script = generate_export_script([_spec()], now=FIXED)
        assert "USERDATA" not in script
        assert "userdata=" not in script.split("for input_file in INPUT_FILES:")[1]

    def test_profile_index_dict_emitted_only_when_nonzero(self) -> None:
        """PROFILE_INDEX is emitted for a selected non-zero profile, omitted otherwise."""
        script_zero = generate_export_script([_spec(profile_index=0)], now=FIXED)
        assert "PROFILE_INDEX" not in script_zero
        assert "profile_index=" not in script_zero.split("for input_file in INPUT_FILES:")[1]

        script_multi = generate_export_script(
            [_spec(is_multi_profile=True, profile_index=2)], now=FIXED
        )
        assert "PROFILE_INDEX = {" in script_multi
        assert "profile_index=PROFILE_INDEX.get(input_file, 0)," in script_multi
        assert ": 2," in script_multi

    def test_output_uses_stem_and_output_dir(self) -> None:
        script = generate_export_script([_spec()], now=FIXED)
        assert 'input_file.stem + ".nc"' in script
        assert "OUTPUT_DIR / " in script

    def test_multiple_files_all_appear_in_input_files(self) -> None:
        jobs = [
            _spec(source=_ROOT / "in" / "a.vec", output=_ROOT / "out" / "a.nc"),
            _spec(source=_ROOT / "in" / "b.vec", output=_ROOT / "out" / "b.nc"),
            _spec(source=_ROOT / "in" / "c.vec", output=_ROOT / "out" / "c.nc"),
        ]
        script = generate_export_script(jobs, now=FIXED)
        for name in ("a.vec", "b.vec", "c.vec"):
            assert name in script
        assert script.count("Path(") >= 3  # at least one per INPUT_FILES entry

    def test_generated_script_is_valid_python(self) -> None:
        """Catch template typos and escape-sequence bugs with compile()."""
        script = generate_export_script(
            [
                _spec(),
                _spec(
                    source=_ROOT / "in" / "b.vec",
                    output=_ROOT / "out" / "b.nc",
                    is_multi_profile=True,
                    profile_index=1,
                    userdata_mode=UserdataMode.EXPLICIT,
                    userdata_path=_ROOT / "etc" / "g.json",
                ),
                _spec(
                    source=_ROOT / "in" / "c.vec",
                    output=_ROOT / "out" / "c.nc",
                    userdata_mode=UserdataMode.SKIP,
                ),
                _spec(
                    source=_ROOT / "in" / "d.vec",
                    output=_ROOT / "out" / "d.nc",
                    userdata_mode=UserdataMode.DICT,
                    userdata_dict={"instrument": "adcp", "depth": 10},
                ),
            ],
            now=FIXED,
        )
        compile(script, "<generated>", "exec")

    def test_empty_job_list_still_valid_python(self) -> None:
        """A zero-job batch should still produce a compilable script."""
        script = generate_export_script([], now=FIXED)
        compile(script, "<generated>", "exec")
        assert "INPUT_FILES = [" in script
        assert "USERDATA" not in script

    def test_path_with_spaces_is_escaped(self) -> None:
        """repr() must produce a valid string literal for paths with spaces."""
        script = generate_export_script(
            [
                _spec(
                    source=_ROOT / "in" / "with spaces" / "a.vec",
                    output=_ROOT / "out" / "with spaces" / "a.nc",
                )
            ],
            now=FIXED,
        )
        compile(script, "<generated>", "exec")
        assert "with spaces" in script

    def test_path_with_quote_is_escaped(self) -> None:
        """Paths containing single quotes must still compile."""
        script = generate_export_script(
            [_spec(source=_ROOT / "in" / "o'brien" / "a.vec")], now=FIXED
        )
        compile(script, "<generated>", "exec")

    def test_loop_body_present(self) -> None:
        script = generate_export_script([_spec()], now=FIXED)
        assert "for input_file in INPUT_FILES:" in script
        assert "process_one_file(" in script
        assert 'output_file = OUTPUT_DIR / (input_file.stem + ".nc")' in script
        assert 'print(f"Saved {output_file}")' in script


class TestIncludeVelds:
    def test_pipeline_always_embedded(self) -> None:
        """The portable pipeline (both functions) is embedded verbatim."""
        script = generate_export_script([_spec()], now=FIXED)
        assert "def process_one_file(" in script
        assert "def inject_derived_velocity(" in script

    def test_default_sets_include_velds_true(self) -> None:
        script = generate_export_script([_spec()], now=FIXED)
        assert "INCLUDE_VELDS = True" in script
        assert "include_velds=INCLUDE_VELDS," in script

    def test_false_sets_include_velds_false(self) -> None:
        script = generate_export_script([_spec(include_velds=False)], now=FIXED)
        assert "INCLUDE_VELDS = False" in script

    def test_any_job_true_enables_velds_for_whole_batch(self) -> None:
        """include_velds is a single batch-level flag, not per-job."""
        script = generate_export_script(
            [_spec(include_velds=False), _spec(include_velds=True)], now=FIXED
        )
        assert "INCLUDE_VELDS = True" in script

    def test_embedded_pipeline_has_no_mhkit_dolfyn_gui_import(self) -> None:
        script = generate_export_script([_spec()], now=FIXED)
        assert "import mhkit_dolfyn_gui" not in script
        assert "from mhkit_dolfyn_gui" not in script

    def test_internal_module_docstring_is_stripped(self) -> None:
        """The embed-safety maintainer notes must not leak into user scripts."""
        script = generate_export_script([_spec()], now=FIXED)
        assert "Embed-safety rules" not in script

    def test_generated_script_with_velds_is_valid_python(self) -> None:
        import ast

        script = generate_export_script([_spec()], now=FIXED)
        ast.parse(script)  # raises SyntaxError on failure
