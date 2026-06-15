"""ffmpeg 二进制管理 - Android 端首次启动自动下载
ffmpeg-kit 提供的预编译 Android 二进制 (约 50MB)
"""
from __future__ import annotations
import os
import sys
import shutil
import zipfile
import urllib.request
from pathlib import Path
from typing import Optional


# ffmpeg-kit 全 GPL 构建 (静态)
FFMPEG_KIT_URL = "https://github.com/arthenica/ffmpeg-kit/releases/download/v6.0-2/ffmpeg-kit-full-6.0-2-android-ndk-r25b.zip"


def _android_bin_dir() -> Path:
    """获取 app 私有目录 /data/data/<pkg>/files/app/bin"""
    if os.environ.get("ANDROID_APP_PATH"):
        return Path(os.environ["ANDROID_APP_PATH"]) / "bin"
    try:
        from jnius import autoclass  # type: ignore
        from android.storage import app_storage_path  # type: ignore
        base = Path(app_storage_path())  # /data/data/<pkg>/files
        d = base / "app" / "bin"
        d.mkdir(parents=True, exist_ok=True)
        return d
    except Exception:
        # 桌面或未配置, 回落到当前目录
        return Path(".").resolve() / "bin"


def _exists_under(dir_: Path, name: str) -> Optional[Path]:
    for sub in ("",):
        cand = dir_ / sub / name
        if cand.exists():
            return cand
    return None


def ensure_ffmpeg(on_log=None) -> Optional[str]:
    """确保 ffmpeg 可用. 返回路径或 None.
    桌面端: 复用本地 bundled/ffmpeg.exe
    Android端: 首次启动时从 ffmpeg-kit 下载
    """
    log = on_log or (lambda m: print(m))

    # 1) 桌面端 bundled 优先
    if not _is_android():
        bundled = Path(__file__).resolve().parent.parent.parent / "bundled" / "ffmpeg.exe"
        if bundled.exists():
            return str(bundled)
        # PATH
        from shutil import which
        p = which("ffmpeg")
        if p:
            return p
        log("[提示] 桌面端未找到 ffmpeg, 请将 ffmpeg.exe 放入 bundled/ 或加入 PATH")
        return None

    # 2) Android 端
    target_dir = _android_bin_dir()
    target = target_dir / "ffmpeg"
    if target.exists() and target.stat().st_size > 1_000_000:
        # 已有, 标可执行
        try:
            target.chmod(0o755)
        except Exception:
            pass
        log(f"[OK] ffmpeg 已就绪: {target}")
        return str(target)

    target_dir.mkdir(parents=True, exist_ok=True)
    log("[下载] 首次启动, 下载 ffmpeg for Android (~50MB)…")

    zip_path = target_dir / "ffmpeg-kit.zip"
    try:
        urllib.request.urlretrieve(FFMPEG_KIT_URL, zip_path)
    except Exception as e:
        log(f"[错误] 下载失败: {e}")
        log("        请检查网络, 或手动放置 ffmpeg 到 /data/data/<pkg>/files/app/bin/ffmpeg")
        return None

    log("[解压] ffmpeg-kit.zip …")
    try:
        with zipfile.ZipFile(zip_path) as z:
            for member in z.namelist():
                if member.endswith("/ffmpeg") or member == "ffmpeg":
                    with z.open(member) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    break
    except Exception as e:
        log(f"[错误] 解压失败: {e}")
        return None

    try:
        target.chmod(0o755)
    except Exception:
        pass
    try:
        zip_path.unlink()
    except Exception:
        pass

    log(f"[完成] ffmpeg 已就绪: {target}")
    return str(target)


def _is_android() -> bool:
    return sys.platform == "linux" and "ANDROID_APP_PATH" in os.environ
