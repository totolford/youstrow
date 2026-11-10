# PyInstaller — build reproductible : .\build.ps1
import os
a = Analysis(
    ["run_youstrow.py"],
    pathex=["."],
    datas=[("youstrow/resources", "youstrow/resources"), ("assets/youstrow.png", "assets")],
    binaries=[("vendor/ftd2xx.dll", ".")],          # driver FTDI D2XX (Open DMX), redistribué avec l'application
    hiddenimports=["serial.tools.list_ports_windows", "rtmidi", "PySide6.QtWebChannel", "PySide6.QtSvg"],
    excludes=["tkinter", "numpy", "pytest", "PySide6.Qt3DCore", "PySide6.QtPdf", "PySide6.QtSql", "PySide6.QtCharts"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="YouStrow", console=bool(os.environ.get("YOUSTROW_CONSOLE")),
          upx=False, icon="assets/youstrow.ico")
coll = COLLECT(exe, a.binaries, a.datas, name="YouStrow", upx=False)
