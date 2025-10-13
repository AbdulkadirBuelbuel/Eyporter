# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Hidden imports required (explicit list for reliability inside PyInstaller)
hiddenimports = [
    'prometheus_client',
    'prometheus_client.core',
    'prometheus_client.exposition',
    'prometheus_client.metrics',
    'prometheus_client.registry',
    'prometheus_client.samples',
    'prometheus_client.utils',
    'prometheus_client.parser',
    'yaml',
    'username_location_mapper',
    'collections.abc',
    '_strptime',
]

# Data files bundled alongside executable
datas = [
    ('mapping.json', '.'),
    ('servers.yml', '.'),
    ('requirements.txt', '.'),
    ('username_location_mapper.py', '.'),
]

# Bundle lmutil.exe (prefer local copy to avoid absolute path dependency)
binaries = [
    ('lmutil.exe', '.'),
]

a = Analysis(
    ['flexlm_exporter.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FlexLM_Exporter',
    debug=False,  # Release mode (no debug overhead)
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Keep False to avoid potential issues with corporate AV
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
