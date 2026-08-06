# MHKiT-DOLFyN GUI

A desktop GUI for reading, inspecting, and exporting ADCP and ADV binary instrument data to standardized NetCDF (`.nc`) files. Powered by [`mhkit.dolfyn`](https://mhkit-software.github.io/MHKiT/mhkit-python/api.dolfyn.html), the Doppler Oceanographic Library for Python included in [MHKiT-Python](https://github.com/MHKiT-Software/MHKiT-Python).

![Overview](docs/img/v0.2.0_overview.png)

## Installation

MHKiT-DOLFyN GUI requires [Python 3.11+](https://www.python.org/) if running from source. It is
recommended to use [Miniconda](https://docs.anaconda.com/miniconda/) or the
[Anaconda Python Distribution](https://www.anaconda.com/distribution/).

### Option 1: Download the Desktop Application

The easiest way to get started — no Python installation required. Grab the latest build for your
platform from the [Releases page](https://github.com/MHKiT-Software/mhkit_dolfyn_pyqt_gui/releases):

- **[Download for Windows](https://github.com/MHKiT-Software/mhkit_dolfyn_pyqt_gui/releases/latest/download/MHKiT-DOLFyN-Windows.exe)**
- **[Download for macOS (Apple Silicon)](https://github.com/MHKiT-Software/mhkit_dolfyn_pyqt_gui/releases/latest/download/MHKiT-DOLFyN-macOS-AppleSilicon.zip)**
- **[Download for macOS (Intel)](https://github.com/MHKiT-Software/mhkit_dolfyn_pyqt_gui/releases/latest/download/MHKiT-DOLFyN-macOS-Intel.zip)**
- **[Download for Linux](https://github.com/MHKiT-Software/mhkit_dolfyn_pyqt_gui/releases/latest/download/MHKiT-DOLFyN-Linux)**

**Linux**: after downloading, mark the file executable, then run it:

```bash
chmod +x MHKiT-DOLFyN-Linux
./MHKiT-DOLFyN-Linux
```

Minimal/server-oriented distros may be missing graphics libraries Qt6 needs to start up. If the
app fails to launch, install the required libraries for your distro:

**Debian/Ubuntu:**

```bash
sudo apt-get install -y libopengl0 libglx0 libgl1 libegl1 libxkbcommon-x11-0 \
  libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
  libxcb-render-util0 libxcb-xinerama0 libxcb-xkb1 libdbus-1-3
```

**Fedora/RHEL:**

```bash
sudo dnf install -y mesa-libGL mesa-libEGL libxkbcommon-x11 xcb-util-cursor \
  xcb-util-image xcb-util-keysyms xcb-util-renderutil xcb-util-wm dbus-libs
```

**Arch/Manjaro:**

```bash
sudo pacman -S --needed mesa libglvnd libxkbcommon-x11 xcb-util-cursor \
  xcb-util-image xcb-util-keysyms xcb-util-renderutil xcb-util-wm dbus
```

(Fedora/RHEL: the equivalent packages are `mesa-libGL`, `mesa-libEGL`, and `libxkbcommon-x11`.)

**macOS**: unzip the download and move `MHKiT-DOLFyN.app` to `/Applications` (or wherever you
like). The app isn't signed with a paid Apple Developer certificate, so Gatekeeper will refuse to
open it ("MHKiT-DOLFyN.app is damaged and can't be opened" or "cannot be opened because the
developer cannot be verified"). Clear the quarantine flag once, before first launch:

```bash
xattr -cr /path/to/MHKiT-DOLFyN.app
```

**Windows**: run the `.exe` directly. It also isn't code-signed, so Windows SmartScreen may show a
warning — click **More info** → **Run anyway**.

### Option 2: Run from source (recommended for development)

Clone the repo and create the Conda environment. `environment.yml` installs all runtime
dependencies (mhkit, PySide6, netCDF4, HDF5, PyYAML, psutil), so you can launch immediately
with `run.py` — no package install needed.

```bash
git clone https://github.com/MHKiT-Software/mhkit_dolfyn_pyqt_gui
```

```bash
cd mhkit_dolfyn_pyqt_gui
```

```bash
conda env create -f environment.yml
```

```bash
conda activate mhkit-dolfyn-gui
```

```bash
python run.py
```

### Option 3: Build a standalone app bundle (PyInstaller)

Produces a self-contained `MHKiT-DOLFyN.app` (macOS) or `MHKiT-DOLFyN.exe` (Windows) in `dist/`
that runs without a Python environment. Start from the Option 2 setup steps, then:

```bash
pip install -e ".[dev]"
```

```bash
pyinstaller mhkit_dolfyn.spec --noconfirm
```

The built bundle will be at `dist/MHKiT-DOLFyN/` (or `dist/MHKiT-DOLFyN.app` on macOS).

### Option 4: pip install with CLI entry point

Install the package to get the `mhkit-dolfyn-gui` command available anywhere on your PATH.
Start from the Option 2 setup steps, then:

```bash
pip install -e .
```

Then launch from any directory:

```bash
mhkit-dolfyn-gui
```

## Workflow

### 1. Import files

Browse your filesystem and add binary instrument files to the conversion queue. Files load in
parallel and appear in the queue with a **Ready** status as soon as they are converted into an
intermediate format (xarray Dataset) for analysis prior to export.

| Manufacturer | Instrument                                                                   | Type | Extensions                                |
| ------------ | ---------------------------------------------------------------------------- | ---- | ----------------------------------------- |
| Nortek       | Signature                                                                    | ADCP | `.ad2cp`                                  |
| Nortek       | Vector                                                                       | ADV  | `.vec`                                    |
| Nortek       | AWAC                                                                         | ADCP | `.wpr`                                    |
| Teledyne RDI | Workhorse, RiverPro, [and others](https://www.teledynemarine.com/brands/rdi) | ADCP | `.000` `.ens` `.enx` `.lta` `.pd0` `.sta` |

![File Import](docs/img/v0.2.0_file_import.png)

### 2. Review datasets

The **Review** panel shows a dataset summary for each file. Switch to the **Per-File** tab to
browse every variable, dimension, and coordinate axis; click any variable to see its shape, type,
statistics, and sample values.

![Per-File Summary](docs/img/v0.2.0_per_file_summary.png)

When multiple files are loaded, the **Combined** tab gives a deployment-level overview: total
time coverage, ensemble counts, and automatic warnings for instrument mismatches, coordinate-system
differences, or unexpected time gaps between files.

![Combined Summary](docs/img/v0.2.0_combined_summary.png)

### 3. Add deployment metadata (optional)

Use the **Custom Deployment Metadata** editor to create or attach a `userdata.json` sidecar file.
This lets you supply information the binary file cannot record — magnetic declination (required for
true-north ENU rotations), deployment coordinates, instrument depth, orientation, and salinity.
`mhkit.dolfyn` reads this file automatically alongside the binary data.

![Deployment Metadata](docs/img/v0.2.0_userdata.png)

### 4. Export to NetCDF

Configure an output directory and filename pattern in the **Export** panel, select which files to
include, and click **Export**. Each file is saved as a self-describing NetCDF (`.nc`) using
`mhkit.dolfyn`.

![NetCDF Export](docs/img/v0.2.0_nc_export.png)

**Show Code** generates a standalone Python script that reproduces the exact same conversion —
useful for scripted pipelines or sharing reproducible workflows.

![Generated Script](docs/img/v0.2.0_code_export.png)

### Event log and preferences

The **Event Log** at the bottom of the window logs events with timestamps. Useful for tracking file
processing and exporting actions.

![Event Log](docs/img/v0.2.0_event_log.png)

**Preferences** (status bar → _Preferences_) lets you tune concurrent read threads, the in-memory
dataset cache, time-gap detection thresholds, and default output paths.

![Preferences](docs/img/v0.2.0_settings_preferences.png)

## Development

Install with development dependencies:

```bash
pip install -e ".[dev]"
```

Run tests, linting, and formatting checks:

```bash
ruff check src/ tests/
ruff format --check src/ tests/
pytest -v
```

## Copyright and license

MHKiT-DOLFyN GUI is copyright through the National Laboratory of the Rockies,
Pacific Northwest National Laboratory, and Sandia National Laboratories.
The software is distributed under the Revised BSD License.
See [copyright and license](LICENSE.md) for more information.
