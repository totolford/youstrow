# PyInstaller — build reproductible : .\build.ps1
import os, sys
a = Analysis(
    ["run_youstrow.py"],
    pathex=["."],
    datas=[("youstrow/resources", "youstrow/resources"), ("assets/youstrow.png", "assets")],
    binaries=[("vendor/ftd2xx.dll", ".")] if sys.platform == "win32" else [],   # D2XX Windows redistribué ; sous Linux : libftd2xx.so système ou repli série
    hiddenimports=[*(["serial.tools.list_ports_windows"] if sys.platform == "win32" else ["serial.tools.list_ports_linux"]), "rtmidi", "PySide6.QtWebChannel", "PySide6.QtSvg"],
    excludes=["tkinter", "numpy", "pytest", "PySide6.Qt3DCore", "PySide6.QtPdf", "PySide6.QtSql", "PySide6.QtCharts"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="YouStrow", console=bool(os.environ.get("YOUSTROW_CONSOLE")),
          upx=False, icon="assets/youstrow.ico" if sys.platform == "win32" else None)
coll = COLLECT(exe, a.binaries, a.datas, name="YouStrow", upx=False)
