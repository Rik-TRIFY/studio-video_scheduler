import sys
from cx_Freeze import setup, Executable

build_exe_options = {
    "packages": ["os", "requests", "PyQt5", "json", "datetime", "platform"],
    "excludes": [],
    "include_files": ["version_info.txt", "app.manifest"]
}

setup(
    name = "VideoScheduler",
    version = "1.0",
    description = "TRIFY Video Scheduler Application",
    options = {"build_exe": build_exe_options},
    executables = [Executable(
        "studio-video_scheduler.py",
        base="Win32GUI",
        target_name="VideoScheduler.exe",
        copyright="Copyright (c) 2024 TRIFY s.r.o.",
        trademarks="TRIFY s.r.o."
    )]
) 