# PyInstaller onedir build. Only application source and required assets are
# packaged; per-user settings and downloaded AI models stay outside the bundle.
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
for package in ("actions", "config", "core", "memory", "plugins"):
    hiddenimports.extend(collect_submodules(package))

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("actions", "actions"),
        ("core/prompt.txt", "core"),
        ("logo.png", "."),
        ("assets/doom-mark.svg", "assets"),
        ("plugins", "plugins"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "IPython", "notebook", "jupyter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Doom",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="logo.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Doom",
)
