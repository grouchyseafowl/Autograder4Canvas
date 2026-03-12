# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Canvas Autograder (Windows).

Build with:
    cd build/windows
    pyinstaller Autograder4Canvas.spec

Output: dist/Autograder4Canvas/Autograder4Canvas.exe
"""

import os

# SPECPATH is set by PyInstaller to the directory containing this .spec file
# Use it to locate src/ relative to build/windows/
SRC_DIR = os.path.normpath(os.path.join(SPECPATH, '..', '..', 'src'))
ICON_PATH = os.path.join(SPECPATH, 'Autograder4Canvas', 'icon.ico')

a = Analysis(
    [os.path.join(SRC_DIR, 'run_autograder.py')],
    pathex=[SRC_DIR],
    binaries=[],
    datas=[
        (os.path.join(SRC_DIR, 'Programs', '*.py'), 'Programs'),
        (os.path.join(SRC_DIR, 'autograder_utils.py'), '.'),
        (os.path.join(SRC_DIR, 'requirements.txt'), '.'),
        (os.path.join(SRC_DIR, 'config'), 'config'),
        (os.path.join(SRC_DIR, 'modules'), 'modules'),
        (os.path.join(SRC_DIR, 'docs'), 'docs'),
    ],
    hiddenimports=[
        'requests',
        'dateutil',
        'pytz',
        'openpyxl',
        'pandas',
        'yaml',
        'tkinter',
        'tkinter.filedialog',
        'json',
        'csv',
        'webbrowser',
        'urllib.parse',
        'modules',
        'modules.assignment_config',
        'modules.citation_verifier',
        'modules.consent_system',
        'modules.context_analyzer',
        'modules.demographic_collector',
        'modules.draft_comparison',
        'modules.feedback_tracker',
        'modules.human_presence_detector',
        'modules.marker_loader',
        'modules.organizational_analyzer',
        'modules.peer_comparison',
        'modules.report_generator',
        'modules.telemetry_manager',
        'modules.update_checker',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Autograder4Canvas',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=ICON_PATH if os.path.exists(ICON_PATH) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Autograder4Canvas',
)
