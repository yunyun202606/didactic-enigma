"""FFmpeg 探测 - 跨平台 (Windows / Android / Linux)
Android 端 ffmpeg 二进制通过 buildozer 打包进 APK, 位于 /data/data/<pkg>/files/app/bin/ffmpeg
"""
from __future__ import annotations

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List


def _exe_name() -> str:
    return "ffmpeg.exe" if os.name == "nt" else "ffmpeg"


def _ffprobe_name() -> str:
    return "ffprobe.exe" if os.name == "nt" else "ffprobe"


def _bundled_dir() -> Optional[Path]:
    """返回本地 bundled/ 目录 (开发/桌面环境)"""
    return Path(__file__).resolve().parent.parent.parent / "bundled"


def _android_app_dir() -> Optional[Path]:
    """Android 私有目录"""
    if not getattr(sys, "is_android", False) and "ANDROID_APP_PATH" not in os.environ:
        return None
    base = os.environ.get("ANDROID_APP_PATH")
    if base:
        return Path(base)
    # Kivy/pyjnius 通用方式
    try:
        from jnius import autoclass  # type: ignore
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        ctx = PythonActivity.mActivity
        files_dir = ctx.getFilesDir().getAbsolutePath()
        return Path(files_dir) / "app"
    except Exception:
        return None


def find_ffmpeg() -> Optional[str]:
    # 1) PATH 中
    p = shutil.which("ffmpeg")
    if p:
        return p
    # 2) Android app 私有目录
    ad = _android_app_dir()
    if ad:
        for sub in ("bin", ""):
            cand = ad / sub / _exe_name()
            if cand.exists():
                return str(cand)
    # 3) 本地 bundled (开发环境)
    bd = _bundled_dir()
    if bd:
        for sub in ("bundled", "ffmpeg", "."):
            cand = bd / sub / _exe_name()
            if cand.exists():
                return str(cand)
    # 4) PyInstaller _MEIPASS (桌面端)
    if getattr(sys, "frozen", False):
        meipass = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        for sub in ("bundled", "ffmpeg", "bin", "."):
            cand = meipass / sub / _exe_name()
            if cand.exists():
                return str(cand)
    # 5) 常见系统路径
    if os.name == "nt":
        candidates = [
            Path("C:/ffmpeg"), Path("C:/ffmpeg/bin"),
            Path(os.environ.get("LOCALAPPDATA", "")) / "ffmpeg" / "bin",
            Path(os.environ.get("ProgramFiles", "")) / "ffmpeg" / "bin",
        ]
        for d in candidates:
            cand = d / _exe_name()
            if cand.exists():
                return str(cand)
    else:
        candidates = [Path("/system/bin"), Path("/vendor/bin"),
                      Path("/data/local/tmp"), Path("/opt/homebrew/bin"),
                      Path("/usr/local/bin"), Path("/usr/bin")]
        for d in candidates:
            cand = d / _exe_name()
            if cand.exists():
                return str(cand)
    return None


def get_ffmpeg_path() -> str:
    p = find_ffmpeg()
    if not p:
        raise FileNotFoundError(
            "未找到 ffmpeg。请将 ffmpeg 放入系统 PATH, "
            "或置于 bundled/ (桌面) / app/bin/ (Android) 目录。"
        )
    return p


def get_ffprobe_path() -> str:
    try:
        ff = get_ffmpeg_path()
    except FileNotFoundError:
        return ""
    probe = Path(ff).parent / _ffprobe_name()
    if probe.exists():
        return str(probe)
    p = shutil.which("ffprobe")
    return p or ""


def get_version() -> str:
    try:
        out = subprocess.run(
            [get_ffmpeg_path(), "-version"],
            capture_output=True, text=True, timeout=10
        )
        line = out.stdout.splitlines()[0] if out.stdout else "未知版本"
        return line
    except Exception as e:
        return f"错误: {e}"


def is_available() -> bool:
    return find_ffmpeg() is not None
