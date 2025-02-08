import sys
from cx_Freeze import setup, Executable

# Základné nastavenia
build_exe_options = {
    "packages": ["os", "sys", "requests", "PyQt5", "json", "datetime", "platform"],
    "includes": ["PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets"],
    "excludes": ["tkinter", "unittest"],
    "include_msvcr": True,
    "zip_include_packages": ["*"],
    "zip_exclude_packages": []
}

# Základná konfigurácia
base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(
    name = "VideoScheduler",
    version = "1.0",
    description = "TRIFY Video Scheduler Application",
    options = {"build_exe": build_exe_options},
    executables = [Executable(
        "studio-video_scheduler.py",
        base=base,
        target_name="VideoScheduler.exe"
    )]
) 