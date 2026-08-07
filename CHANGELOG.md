# v0.3.2: MHKiT 1.1.1

### Bug Fixes

- Bumped MHKiT to `>=1.1.1`, which fixes a Nortek reader edge case for data files with an odd number of bins (MHKiT-Python #459).

### Notes

- v0.3.1 was never published. A GitHub Actions outage on 2026-08-06 dropped the `main` push event that produces release builds, so no `v0.3.1` tag or binaries exist. The v0.3.1 Linux CI fix ships in this release.

# v0.3.1: Linux CI Smoke Test Fix

### Bug Fixes

- Fixed Linux CI failing with exit 126 (`Not a directory`) on every push-triggered release/prerelease build. The "Smoke test bundled app" step hardcoded the onedir executable path (`dist/MHKiT-DOLFyN/MHKiT-DOLFyN`), but push builds to `main`/`develop` produce a single-file executable (`dist/MHKiT-DOLFyN`) via `PYINSTALLER_ONEFILE`. The step now detects onefile vs. onedir output and launches the correct path.

# v0.3.0: Derived Variable Support

## Additions

- Derived variable support (`velds`)
  - Compute velocity/turbulence-derived variables and save in output `.nc` files. `velds` settings are exposed in the workflow config, export sidebar, and codegen/export pipeline.
- Nortek Aquadopp and Aquadopp Profiler support (`.aqd` / `.prf`), added upstream in MHKiT 1.1.0.

## Improvements

- Export pipeline code now embedded directly rather than generated as a string.
- Linux CI now installs graphics libraries required for the app to run headless.
- Bumped MHKiT to `>=1.1.0`, installed via pip instead of conda-forge.

### Bug Fixes


- Fixed a Windows PySide6 import/runtime crash (`from PySide6.QtCore import QTimer`) by switching `environment.yml` to a conda-built PySide6 package instead of the pip build (addresses issue #6).
