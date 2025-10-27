# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['adcp_converter_app.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'mhkit',
        'mhkit.dolfyn',
        'mhkit.dolfyn.io',
        'mhkit.dolfyn.adp',
        'netCDF4',
        'h5py',
        'matplotlib.backends.backend_qtagg',
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
    a.binaries,
    a.datas,
    [],
    name='MHKiT DOLFyN',
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
)
app = BUNDLE(
    exe,
    name='MHKiT DOLFyN.app',
    icon=None,
    bundle_identifier='gov.nrel.mhkit',
)
