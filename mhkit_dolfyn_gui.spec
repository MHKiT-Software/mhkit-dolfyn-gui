# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import shutil
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

# App naming - change these to customize the output
APP_NAME = 'MHKiT-DOLFyN'  # Used for executable and folder names
APP_BUNDLE_NAME = 'MHKiT-DOLFyN.app'  # macOS app bundle name
BUNDLE_ID = 'gov.nrel.mhkit.dolfyn'

# Single-file mode: Set PYINSTALLER_ONEFILE=true to build a single executable
# This is used for prerelease builds on Windows and Linux
# macOS always uses .app bundle regardless of this setting
ONEFILE = os.environ.get('PYINSTALLER_ONEFILE', '').lower() == 'true'
if ONEFILE:
    print(f"Building in SINGLE-FILE mode (PYINSTALLER_ONEFILE={os.environ.get('PYINSTALLER_ONEFILE')})")

# App icon (platform-specific) - Using proper square DOLFyN icons
if sys.platform == 'darwin':
    APP_ICON = 'assets/app_icon/macos/AppIcon.icns' if Path('assets/app_icon/macos/AppIcon.icns').exists() else None
elif sys.platform == 'win32':
    APP_ICON = 'assets/app_icon/windows/AppIcon.ico' if Path('assets/app_icon/windows/AppIcon.ico').exists() else None
else:
    APP_ICON = None  # Linux uses .desktop files for icons

# Collect pecos templates directory
pecos_data_paths = collect_data_files('pecos')

# Static assets to bundle (icons, version info, etc.)
static_asset_paths = [
    ('assets/MHKiT_logo.png', 'assets'),
    ('assets/linux', 'assets/linux'),  # Status bar icons
    ('assets/app_icon/linux', 'assets/app_icon/linux'),  # Window icons
    ('pyproject.toml', '.'),  # Version info
]

# Platform-specific library handling for macOS jpeg issue
jpeg_binaries = []
conda_prefix = os.environ.get('CONDA_PREFIX', '')
if conda_prefix and sys.platform == 'darwin':
    lib_dir = Path(conda_prefix) / 'lib'
    # macOS: Find jpeg library and ensure it's bundled
    # Try libjpeg.9 first, then libjpeg.8, then libjpeg-turbo variants
    for jpeg_name in ['libjpeg.9.dylib', 'libjpeg.8.dylib', 'libjpeg.62.dylib']:
        jpeg_path = lib_dir / jpeg_name
        if jpeg_path.exists():
            jpeg_binaries = [(str(jpeg_path), '.')]
            print(f"Found jpeg library: {jpeg_path}")
            break

# Packages to exclude - these are either unused or have large unused components
EXCLUDES = [
    'PySide6',
    # sklearn is not used by dolfyn
    'sklearn',
    'scikit-learn',
    # Unused test frameworks and testing utilities
    'pytest',
    'pytest_cov',
    'coverage',
    'hypothesis',
    'unittest',
    # Development tools not needed at runtime
    'pip',
    'setuptools',
    'wheel',
    'pkg_resources',
    # Unused matplotlib backends
    'matplotlib.backends.backend_tkagg',
    'matplotlib.backends.backend_gtk3agg',
    'matplotlib.backends.backend_gtk4agg',
    'matplotlib.backends.backend_wxagg',
    'matplotlib.backends.backend_cairo',
    'matplotlib.backends.backend_pdf',
    'matplotlib.backends.backend_pgf',
    'matplotlib.backends.backend_ps',
    'matplotlib.backends.backend_svg',
    'matplotlib.backends.backend_webagg',
    'matplotlib.backends.backend_nbagg',
    # Tkinter
    'tkinter',
    '_tkinter',
    'Tkinter',
    # IPython/Jupyter
    'IPython',
    'jupyter',
    'notebook',
    'ipykernel',
    'ipywidgets',
    # Unused Qt modules
    'PyQt6.QtBluetooth',
    'PyQt6.QtDBus',
    'PyQt6.QtDesigner',
    'PyQt6.QtHelp',
    'PyQt6.QtMultimedia',
    'PyQt6.QtMultimediaWidgets',
    'PyQt6.QtNetwork',
    'PyQt6.QtNfc',
    'PyQt6.QtOpenGL',
    'PyQt6.QtOpenGLWidgets',
    'PyQt6.QtPositioning',
    'PyQt6.QtPrintSupport',
    'PyQt6.QtQml',
    'PyQt6.QtQuick',
    'PyQt6.QtQuickWidgets',
    'PyQt6.QtRemoteObjects',
    'PyQt6.QtSensors',
    'PyQt6.QtSerialPort',
    'PyQt6.QtSpatialAudio',
    'PyQt6.QtSql',
    'PyQt6.QtTest',
    'PyQt6.QtWebChannel',
    'PyQt6.QtWebEngineCore',
    'PyQt6.QtWebEngineQuick',
    'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtWebSockets',
    'PyQt6.QtXml',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=jpeg_binaries,
    datas=pecos_data_paths + static_asset_paths,
    hiddenimports=[
        'mhkit',
        'mhkit.dolfyn',
        'mhkit.dolfyn.io',
        'mhkit.dolfyn.io.api',
        'mhkit.dolfyn.adp',
        'mhkit.dolfyn.adp.api',
        'mhkit.dolfyn.adp.clean',
        'mhkit.dolfyn.adv',
        'mhkit.dolfyn.adv.api',
        'mhkit.dolfyn.adv.clean',
        'mhkit.dolfyn.velocity',
        'netCDF4',
        'h5py',
        'matplotlib.backends.backend_qtagg',
        'components',
        'components.modes',
        'components.modes.standardize_mode',
        'components.help_system',
        'components.batch_processor',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# Single-file mode for Windows/Linux prereleases
# macOS always uses .app bundle (directory mode required)
if ONEFILE and sys.platform != 'darwin':
    # Single executable - all dependencies bundled inside
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=APP_ICON,
    )
    # No COLLECT needed for single-file mode
    coll = None
else:
    # Directory mode - separate folder with dependencies
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
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=APP_ICON,
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name=APP_NAME,
    )

# macOS: Create .app bundle (requires directory mode)
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name=APP_BUNDLE_NAME,
        icon=APP_ICON,
        bundle_identifier=BUNDLE_ID,
    )

    # Post-build: Ensure libjpeg.8.dylib exists (create symlink if needed)
    frameworks_dir = Path(f'dist/{APP_BUNDLE_NAME}/Contents/Frameworks')
    macos_dir = Path(f'dist/{APP_BUNDLE_NAME}/Contents/MacOS')

    for check_dir in [frameworks_dir, macos_dir]:
        if not check_dir.exists():
            continue

        jpeg8 = check_dir / 'libjpeg.8.dylib'
        if jpeg8.exists():
            print(f"✓ libjpeg.8.dylib already exists in {check_dir.name}")
            continue

        # Try to create symlink from available jpeg library
        for source_name in ['libjpeg.9.dylib', 'libjpeg.62.dylib']:
            source = check_dir / source_name
            if source.exists():
                try:
                    os.symlink(source_name, jpeg8)
                    print(f"✓ Created symlink: {jpeg8} -> {source_name}")
                    break
                except Exception as e:
                    print(f"⚠ Could not create symlink: {e}")
