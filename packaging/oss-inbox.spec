# PyInstaller build of one oss-inbox executable. Run from the repo root:
#   pyinstaller packaging/oss-inbox.spec
# The executable is in dist/.

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.dirname(SPECPATH)

# Textual and Rich import some modules lazily. PyInstaller cannot find those itself.
hidden = collect_submodules("textual") + collect_submodules("rich")
datas = [(os.path.join(ROOT, "ossinbox", "static"), "ossinbox/static")]
datas += collect_data_files("textual")

a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],
    pathex=[ROOT],
    datas=datas,
    hiddenimports=hidden,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="oss-inbox",
    console=True,
    upx=False,
)
