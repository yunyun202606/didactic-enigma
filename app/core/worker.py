"""FFmpeg 后台执行线程 + 进度解析"""
from __future__ import annotations

import re
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QObject, Signal


@dataclass
class FFmpegJob:
    args: List[str]
    input_files: List[Path] = field(default_factory=list)
    output_file: Optional[Path] = None
    name: str = "任务"


class FFmpegWorker(QObject):
    log_signal = Signal(str)
    progress_signal = Signal(float)  # 0..1
    finished_signal = Signal(bool, str)  # success, message

    def __init__(self, job: FFmpegJob, total_duration: Optional[float] = None):
        super().__init__()
        self.job = job
        self.total_duration = total_duration
        self._process: Optional[subprocess.Popen] = None
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
            except Exception:
                pass

    def _emit(self, line: str):
        if line:
            self.log_signal.emit(line)

    def _parse_time(self, line: str) -> Optional[float]:
        m = re.search(r"time=(\d+):(\d+):(\d+\.?\d*)", line)
        if not m:
            return None
        try:
            h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
            return h * 3600 + mi * 60 + s
        except Exception:
            return None

    def _probe_duration(self, file_path: Path) -> Optional[float]:
        try:
            from . import ffmpeg as _ff
            probe_path = _ff.get_ffprobe_path()
            if not probe_path:
                return None
            out = subprocess.run(
                [probe_path, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)],
                capture_output=True, text=True, timeout=10
            )
            v = out.stdout.strip()
            return float(v) if v else None
        except Exception:
            return None

    def run(self):
        if self._cancelled:
            self.finished_signal.emit(False, "已取消")
            return
        if not self.job.input_files and not self.job.output_file:
            self.finished_signal.emit(False, "任务缺少必要参数")
            return

        # 自动探测总时长
        if self.total_duration is None and self.job.input_files:
            self.total_duration = self._probe_duration(self.job.input_files[0])

        # 准备隐藏控制台
        creationflags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

        try:
            self._process = subprocess.Popen(
                self.job.args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                bufsize=1,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
        except FileNotFoundError as e:
            self._emit(f"[错误] 启动失败: {e}")
            self.finished_signal.emit(False, f"FFmpeg 不可执行: {e}")
            return
        except Exception as e:
            self._emit(f"[错误] {e}")
            self.finished_signal.emit(False, str(e))
            return

        # 读取输出
        assert self._process.stdout is not None
        for line in self._process.stdout:
            if self._cancelled:
                break
            line = line.rstrip()
            if line:
                self._emit(line)
                t = self._parse_time(line)
                if t is not None and self.total_duration and self.total_duration > 0:
                    self.progress_signal.emit(min(1.0, t / self.total_duration))

        rc = self._process.wait()
        if self._cancelled:
            self.finished_signal.emit(False, "已取消")
        elif rc == 0:
            self.progress_signal.emit(1.0)
            self.finished_signal.emit(True, "完成")
        else:
            self.finished_signal.emit(False, f"FFmpeg 退出码 {rc}")
