# -*- mode: python ; coding: utf-8 -*-

"""PyInstaller spec for MHKiT-DOLFyN.

Build with: ``pyinstaller mhkit_dolfyn.spec --noconfirm``

Notes:
- App version is read from ``src/mhkit_dolfyn_gui/_version.py`` so the bundle stays in sync.
- ``collect_data_files`` pulls every ``config/*.yaml`` and ``data/*.json`` from
  the installed package, which is required because the app loads them via
  ``importlib.resources`` (see ``constants.py`` and ``models/summary_template.py``).
- ``collect_submodules('mhkit.dolfyn')`` pulls in all of DOLFyN's IO backends,
  which are loaded dynamically and would otherwise be missed by static analysis.
- ``assets/app_icon`` and ``assets/MHKiT_logo.png`` (splash screen) are
  bundled from ``assets/`` — the rest of that directory is dev-only.
"""

import sys
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

sys.path.insert(0, "src")


def _read_version() -> str:
    """Read the project version from _version.py (single source of truth).

    Falls back to ``0.0.0`` if the import fails so the build never hard-fails
    on a packaging metadata issue.
    """
    try:
        from mhkit_dolfyn_gui._version import __version__
        return __version__
    except Exception:
        return "0.0.0"


APP_NAME = "MHKiT-DOLFyN"
APP_VERSION = _read_version()
BUNDLE_ID = "org.mhkit.dolfyn-gui"

base_path = Path(".")
src_path = base_path / "src"
icon_dir = base_path / "assets" / "app_icon"

# In-package data (yaml/json) loaded via importlib.resources at runtime.
package_datas = collect_data_files(
    "mhkit_dolfyn_gui",
    includes=["config/*.yaml", "data/*.json"],
)

# Runtime icon assets — _set_app_icon() in app.py only reads from app_icon/.
# Splash screen logo — _load_logo() in splash_screen.py reads MHKiT_logo.png.
asset_datas = [
    (str(icon_dir), "assets/app_icon"),
    (str(base_path / "assets" / "MHKiT_logo.png"), "assets"),
]

datas = package_datas + asset_datas

# DOLFyN backends are loaded dynamically; collect them all.
hiddenimports = collect_submodules("mhkit.dolfyn") + [
    "mhkit",
    "netCDF4",
    "cftime",
    "xarray",
    "numpy",
    "pandas",
    "scipy",
    "yaml",
]

excludes = [
    # matplotlib is not used in the qt application
    # but importing any mhkit module requires matplotlib
    # "matplotlib",
    "tkinter",
    "IPython",
    "jupyter",
    "notebook",
]

if sys.platform == "darwin":
    icon_file = str(icon_dir / "macos" / "AppIcon.icns")
elif sys.platform == "win32":
    icon_file = str(icon_dir / "windows" / "AppIcon.ico")
else:
    icon_file = None

block_cipher = None

a = Analysis(
    [str(src_path / "mhkit_dolfyn_gui" / "app.py")],
    pathex=[str(src_path)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    # CI builds per-runner-arch; universal2 needs lipo'd PySide6 wheels.
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon_file,
        bundle_identifier=BUNDLE_ID,
        info_plist={
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "NSHighResolutionCapable": True,
            "NSPrincipalClass": "NSApplication",
            "NSHumanReadableCopyright": "BSD-3-Clause",
        },
    )
