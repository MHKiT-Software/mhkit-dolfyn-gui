# v0.3.0: Derived Variable Support

## Additions

- Derived variable support (`velds`)
  - Compute velocity/turbulence-derived variables and save in output `.nc` files. `velds` settings are exposed in the workflow config, export sidebar, and codegen/export pipeline.

## Improvements

- Export pipeline code now embedded directly rather than generated as a string.
- Linux CI now installs graphics libraries required for the app to run headless.

### Bug Fixes


- Fixed a Windows PySide6 import/runtime crash (`from PySide6.QtCore import QTimer`) by switching `environment.yml` to a conda-built PySide6 package instead of the pip build (addresses issue #6).
