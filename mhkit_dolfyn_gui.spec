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

# App icon (platform-specific) - Using proper square DOLFyN icons
if sys.platform == 'darwin':
    APP_ICON = 'assets/app_icon/macos/AppIcon.icns' if Path('assets/app_icon/macos/AppIcon.icns').exists() else None
elif sys.platform == 'win32':
    APP_ICON = 'assets/app_icon/windows/AppIcon.ico' if Path('assets/app_icon/windows/AppIcon.ico').exists() else None
else:
    APP_ICON = None  # Linux uses .desktop files for icons

# Collect pecos templates directory
pecos_datas = collect_data_files('pecos')

# Add logo for splash screen and status bar icons
logo_datas = [
    ('assets/MHKiT_logo.png', 'assets'),
    ('assets/linux', 'assets/linux'),  # Status bar icons
    ('assets/app_icon/linux', 'assets/app_icon/linux'),  # Window icons
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

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=jpeg_binaries,
    datas=pecos_datas + logo_datas,
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
    excludes=['PySide6'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

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
    icon=APP_ICON,  # Windows uses icon here
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

# macOS: Create .app bundle
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
