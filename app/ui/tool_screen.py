"""工具屏 - 参数 + 文件 + 执行 + 进度 + 日志
Kivy 版, 复用 core.tools 的 build_args / core.worker 的 FFmpegWorker
"""
from __future__ import annotations
import os
import threading
import time
from pathlib import Path
from typing import Dict, Any
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.metrics import dp
from kivy.clock import Clock, mainthread
from kivy.utils import platform

from app.ui import theming as T
from app.ui.widgets import ParamRow, FilePickerPopup, ProgressLogBox
from app.core.worker import FFmpegWorker, FFmpegJob
from app.core import ffmpeg as ffm


def _output_dir() -> Path:
    """Android: 公共下载目录; 桌面: 用户下载目录; 否则当前目录"""
    if platform == "android":
        try:
            from jnius import autoclass
            Environment = autoclass("android.os.Environment")
            dl = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
            p = Path(dl.getAbsolutePath()) / "流光璃韵"
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            return Path("/sdcard/Download/流光璃韵")
    return Path(os.path.expanduser("~/Downloads/流光璃韵"))


def _input_dir() -> Path:
    if platform == "android":
        return Path("/sdcard")
    return Path(os.path.expanduser("~"))


class ToolScreen(BoxLayout):
    def __init__(self, app, card, **kw):
        super().__init__(orientation="vertical", **kw)
        self.app = app
        self.card = card
        self.tool = card.tool
        self._param_rows: Dict[str, ParamRow] = {}
        self._files: list = []  # 多文件工具用
        self._thread: threading.Thread | None = None
        self._build()

    def _build(self):
        with self.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*T.PAPER)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd_bg, size=self._upd_bg)

        # 顶部导航
        nav = BoxLayout(size_hint_y=None, height=dp(48), padding=(dp(8), dp(4)), spacing=dp(8))
        with nav.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(*T.INDIGO)
            self._nav_rect = RoundedRectangle(pos=nav.pos, size=nav.size, radius=[0])
        nav.bind(pos=lambda w, *_: setattr(self._nav_rect, "pos", w.pos),
                 size=lambda w, *_: setattr(self._nav_rect, "size", w.size))

        back = Button(text="← 返回", size_hint_x=None, width=dp(80),
                      background_color=T.ROUGE, color=(1, 1, 1, 1))
        back.bind(on_release=lambda *_: self.app.goto_main())
        nav.add_widget(back)

        title = Label(text=f"{self.card.icon}  {self.card.name}", font_size="16sp", bold=True,
                      color=(1, 1, 1, 1), halign="left", valign="middle")
        title.bind(size=lambda w, _: setattr(w, "text_size", (w.width, w.height)))
        nav.add_widget(title)
        self.add_widget(nav)

        # 滚动主体
        scroll = ScrollView()
        body = BoxLayout(orientation="vertical", size_hint_y=None, padding=dp(10), spacing=dp(8))
        body.bind(minimum_height=body.setter("height"))
        scroll.add_widget(body)
        self.add_widget(scroll)

        # 文件区
        self._file_box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(0),
                                    spacing=dp(4))
        body.add_widget(self._file_box)
        self._build_file_area()

        # 工具说明
        desc = Label(text=self.card.desc, size_hint_y=None, height=dp(22), font_size="11sp",
                     color=T.INDIGO, halign="left", valign="middle")
        desc.bind(size=lambda w, _: setattr(w, "text_size", (w.width, w.height)))
        body.add_widget(desc)

        # TTS 文本框 (单独放在参数上方)
        if self.tool.id == "tts":
            self._build_tts_extra(body)

        # 参数
        self._params_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6),
                                     padding=(0, dp(4), 0, dp(4)))
        self._params_box.bind(minimum_height=self._params_box.setter("height"))
        body.add_widget(self._params_box)
        self._build_params()

        # 执行按钮
        run_bar = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8), padding=(0, dp(8), 0, 0))
        self._run_btn = Button(text="▶  开始", background_color=T.OR, color=T.INK, bold=True)
        self._run_btn.bind(on_release=lambda *_: self._on_run())
        run_bar.add_widget(self._run_btn)

        self._cancel_btn = Button(text="✕  取消", background_color=T.GRAY, color=(1, 1, 1, 1))
        self._cancel_btn.bind(on_release=lambda *_: self._on_cancel())
        run_bar.add_widget(self._cancel_btn)
        body.add_widget(run_bar)

        # 输出目录提示
        out_hint = Label(text=f"输出: {_output_dir()}", size_hint_y=None, height=dp(18),
                         font_size="10sp", color=T.GRAY)
        out_hint.bind(size=lambda w, _: setattr(w, "text_size", (w.width, w.height)))
        body.add_widget(out_hint)

        # 进度 + 日志
        self._plog = ProgressLogBox()
        body.add_widget(self._plog)

    def _build_file_area(self):
        """根据 input_kind 决定: 单文件 / 多文件 / URL / 文本"""
        ik = self.tool.input_kind
        if ik in ("text",):
            # TTS 已经在 _build_tts_extra 处理
            return
        if ik in ("url",):
            row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(4))
            ti = TextInput(hint_text="输入 URL (http://...)", multiline=False,
                           background_color=(1, 1, 1, 1), foreground_color=T.INK)
            self._url_input = ti
            row.add_widget(ti)
            self._file_box.height = dp(40)
            self._file_box.add_widget(row)
            return

        # 单文件
        if ik in ("video", "audio", "image"):
            self._file_box.height = dp(40)
            row = BoxLayout(spacing=dp(4))
            self._file_input = TextInput(hint_text="选择文件...", multiline=False,
                                          background_color=(1, 1, 1, 1), foreground_color=T.INK)
            btn = Button(text="📁 浏览", size_hint_x=None, width=dp(80), background_color=T.OR)
            btn.bind(on_release=lambda *_: self._pick_file())
            row.add_widget(self._file_input)
            row.add_widget(btn)
            self._file_box.add_widget(row)
        elif ik in ("multi_video", "multi_audio"):
            self._file_box.height = dp(160)
            self._files_list = TextInput(text="", readonly=True,
                                          background_color=(1, 1, 1, 0.6),
                                          foreground_color=T.INK,
                                          size_hint_y=None, height=dp(110))
            bar = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(4))
            add = Button(text="➕ 添加", background_color=T.OR)
            add.bind(on_release=lambda *_: self._pick_multi())
            clr = Button(text="🗑 清空", background_color=T.GRAY)
            clr.bind(on_release=lambda *_: self._clear_files())
            bar.add_widget(add)
            bar.add_widget(clr)
            self._file_box.add_widget(self._files_list)
            self._file_box.add_widget(bar)

    def _build_tts_extra(self, parent):
        # 顶部提示
        tip = Label(text="在下方输入要合成的文本:", size_hint_y=None, height=dp(22),
                    font_size="11sp", color=T.INDIGO, halign="left", valign="middle")
        tip.bind(size=lambda w, _: setattr(w, "text_size", (w.width, w.height)))
        parent.add_widget(tip)
        # 文本框
        self._text_input = TextInput(hint_text="在此输入文本...", multiline=True,
                                      background_color=(1, 1, 1, 1), foreground_color=T.INK,
                                      size_hint_y=None, height=dp(160))
        parent.add_widget(self._text_input)

    def _build_params(self):
        # 清空
        self._params_box.clear_widgets()
        for p in self.tool.params:
            row = ParamRow(p)
            self._param_rows[p.key] = row
            self._params_box.add_widget(row)

    # ========== 文件选择 ==========
    def _pick_file(self):
        def _on(paths):
            if paths:
                self._file_input.text = paths[0]
        fp = FilePickerPopup(title="选择文件", on_select=_on)
        fp.open()

    def _pick_multi(self):
        def _on(paths):
            for p in paths:
                if p not in self._files:
                    self._files.append(p)
            self._refresh_files()
        fp = FilePickerPopup(title="选择多个文件", multi=True, on_select=_on)
        fp.open()

    def _clear_files(self):
        self._files = []
        self._refresh_files()

    def _refresh_files(self):
        self._files_list.text = "\n".join(self._files) if self._files else "(空)"

    # ========== 执行 ==========
    def _collect_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        for k, row in self._param_rows.items():
            params[k] = row.value()
        # TTS 文本
        if self.tool.id == "tts":
            params["text"] = getattr(self, "_text_input", None) and self._text_input.text or ""
        return params

    def _on_run(self):
        if self._thread and self._thread.is_alive():
            return

        params = self._collect_params()

        # 校验
        ik = self.tool.input_kind
        if ik in ("video", "audio", "image"):
            in_path = self._file_input.text.strip() if hasattr(self, "_file_input") else ""
            if not in_path or not Path(in_path).exists():
                self._toast("请先选择有效的输入文件")
                return
            inputs = [Path(in_path)]
        elif ik in ("multi_video", "multi_audio"):
            if not self._files:
                self._toast("请先添加文件")
                return
            inputs = [Path(p) for p in self._files]
        elif ik == "url":
            url = self._url_input.text.strip() if hasattr(self, "_url_input") else ""
            if not url:
                self._toast("请输入 URL")
                return
            inputs = [url]
        elif ik == "text":
            txt = (self._text_input.text or "").strip()
            if not txt:
                self._toast("请输入文本")
                return
            inputs = []
            params["__text__"] = txt
        else:
            inputs = []

        # 检查 ffmpeg
        try:
            ffmpeg_path = ffm.get_ffmpeg_path()
        except FileNotFoundError as e:
            self._toast(str(e))
            return

        out_dir = _output_dir()
        out_dir.mkdir(parents=True, exist_ok=True)

        # 启动线程
        self._plog.set_status("处理中…")
        self._plog.set_progress(0)
        self._plog.append_log(f"▶ 启动 {self.card.name}")
        self._run_btn.disabled = True

        if self.tool.id == "tts":
            self._thread = threading.Thread(target=self._run_tts, args=(params,), daemon=True)
        else:
            self._thread = threading.Thread(target=self._run_ffmpeg,
                                             args=(inputs, params, ffmpeg_path, out_dir),
                                             daemon=True)
        self._thread.start()

    def _on_cancel(self):
        if self._worker:
            self._worker.cancel()
            self._plog.append_log("[已请求取消]")

    def _toast(self, msg):
        self._plog.append_log(f"⚠ {msg}")
        self._plog.set_status(msg)

    # ========== FFmpeg 运行 ==========
    def _run_ffmpeg(self, inputs, params, ffmpeg_path, out_dir):
        from app.core.worker import FFmpegJob
        try:
            if not inputs:
                self._post(False, "没有输入文件")
                return
            out_name = f"{self.tool.id}_{Path(str(inputs[0])).stem}_{int(time.time())}.{self.tool.output_ext}"
            output = out_dir / out_name
            # 探测时长
            total = self._probe_duration(ffmpeg_path, str(inputs[0]))
            # 构造 args
            args_with_output = self.tool.build_args(params, inputs, output)
            # 替换最后一项为真实 output
            if args_with_output and isinstance(args_with_output[-1], str):
                args_with_output = self.tool.build_args(params, inputs, output)
            full_args = [ffmpeg_path, "-y", "-i", str(inputs[0])] + args_with_output

            self._log(f"命令: ffmpeg {' '.join(map(str, full_args[:-1]))} …")

            job = FFmpegJob(full_args, input_files=inputs, output_file=output, name=self.card.name)
            worker = FFmpegWorker(job, total_duration=total)
            self._worker = worker
            worker.log_signal.connect(self._on_log_thread)
            worker.progress_signal.connect(self._on_prog_thread)
            worker.finished_signal.connect(self._on_done_thread)
            worker.run()
        except Exception as e:
            self._post(False, f"运行错误: {e}")

    def _run_tts(self, params):
        # 复用 core.tts 的接口
        try:
            from app.core import tts as tts_mod
            text = params.get("text", "").strip()
            voice = params.get("voice", "zh-CN-XiaoxiaoNeural")
            rate = params.get("rate", "+0%")
            self._log(f"▶ TTS 文本: {text[:30]}…  角色: {voice}")
            out_dir = _output_dir()
            ts = int(time.time())
            out = out_dir / f"tts_{ts}.mp3"
            ok = tts_mod.synthesize_text(text, voice=voice, rate=rate, output=out,
                                          on_log=lambda m: self._log(m))
            if ok:
                self._log(f"✔ 完成 -> {out}")
                self._post(True, f"已生成: {out.name}")
            else:
                self._post(False, "TTS 失败, 请检查网络")
        except Exception as e:
            self._post(False, f"TTS 错误: {e}")

    @staticmethod
    def _probe_duration(ffmpeg_path, in_path):
        import subprocess, re
        try:
            out = subprocess.run([ffmpeg_path, "-i", in_path], capture_output=True,
                                  text=True, timeout=10)
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", out.stderr)
            if m:
                h, mi, s = m.groups()
                return int(h) * 3600 + int(mi) * 60 + float(s)
        except Exception:
            pass
        return None

    # ========== 跨线程回调 ==========
    def _log(self, msg):
        Clock.schedule_once(lambda *_: self._plog.append_log(msg), 0)

    def _set_status(self, msg):
        Clock.schedule_once(lambda *_: self._plog.set_status(msg), 0)

    def _set_progress(self, v):
        Clock.schedule_once(lambda *_: self._plog.set_progress(v), 0)

    def _on_log_thread(self, msg):
        self._log(msg)

    def _on_prog_thread(self, v):
        self._set_progress(v)

    def _on_done_thread(self, ok, msg):
        self._post(ok, msg)

    @mainthread
    def _post(self, ok, msg):
        self._plog.set_status("✔ 完成" if ok else f"✕ 失败: {msg}")
        if ok:
            self._plog.append_log(f"✔ {msg}")
            self._plog.set_progress(100)
        else:
            self._plog.append_log(f"✕ {msg}")
        self._run_btn.disabled = False

    def _upd_bg(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size
