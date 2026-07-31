# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

frida_datas, frida_binaries, frida_hiddenimports = collect_all("frida")

analysis = Analysis(
    ["main.py"],
    pathex=[],
    binaries=frida_binaries,
    datas=frida_datas + [
        ("app/frida_agent.js", "app"),
        ("assets/logo.svg", "assets"),
    ],
    hiddenimports=frida_hiddenimports + ["serial.tools.list_ports_windows"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="CommMonit",
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
    icon=["assets/commmonit.ico"],
    uac_admin=True,
)

collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CommMonit-folder",
)
