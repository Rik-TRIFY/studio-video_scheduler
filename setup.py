import sys
from cx_Freeze import setup, Executable
import os

# Získanie absolútnej cesty k súborom
manifest_file = os.path.abspath("app.manifest")
version_file = os.path.abspath("version_info.txt")

build_exe_options = {
    "packages": ["os", "requests", "PyQt5", "json", "datetime", "platform"],
    "excludes": [],
    "include_files": [],  # Odstránime include_files, ktoré spôsobujú problém
    "include_msvcr": True
}

base = "Win32GUI" if sys.platform == "win32" else None

setup(
    name = "VideoScheduler",
    version = "1.0",
    description = "TRIFY Video Scheduler Application",
    options = {"build_exe": build_exe_options},
    executables = [Executable(
        "studio-video_scheduler.py",
        base=base,
        target_name="VideoScheduler.exe",
        copyright="Copyright (c) 2024 TRIFY s.r.o.",
        trademarks="TRIFY s.r.o."
    )]
) 