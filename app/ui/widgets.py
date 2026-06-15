"""Kivy 自定义控件 - 国风简化版"""
from __future__ import annotations
from typing import Optional, List
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.spinner import Spinner
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.clock import Clock
from kivy.properties import StringProperty, NumericProperty, BooleanProperty, ListProperty, ObjectProperty
from kivy.metrics import dp
from kivy.utils import get_color_from_hex

from app.ui import theming as T


# ============== 工具卡片 ==============
class ToolCardView(BoxLayout):
    """主屏上的工具卡片"""
    def __init__(self, card, on_tap=None, **kw):
        super().__init__(orientation="vertical", size_hint_y=None,
                         height=dp(110), padding=dp(10), spacing=dp(4), **kw)
        self.card = card
        self._on_tap = on_tap

        with self.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            self._bg_color = Color(*card.color)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])

        self.bind(pos=self._upd_rect, size=self._upd_rect)

        top = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))
        top.add_widget(Label(text=card.icon, font_size="22sp", size_hint_x=None, width=dp(36),
                             halign="center", valign="middle", color=(1, 1, 1, 1)))
        top.add_widget(Label(text=card.name, font_size="16sp", bold=True, color=(1, 1, 1, 1),
                             halign="left", valign="middle"))
        self.add_widget(top)

        self.add_widget(Label(text=card.desc, font_size="11sp", color=(1, 1, 1, 0.85),
                              halign="left", valign="top", text_size=(dp(180), dp(40))))

    def _upd_rect(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self._on_tap:
                self._on_tap(self.card)
            return True
        return super().on_touch_down(touch)


# ============== 文件选择器 ==============
class FilePickerPopup(Popup):
    """文件选择弹窗 - 复用 Kivy FileChooser, Android 上 plyer/filechooser 都能用"""
    def __init__(self, title="选择文件", filters=None, multi=False, on_select=None, **kw):
        super().__init__(title=title, size_hint=(0.92, 0.85), **kw)
        self._on_select = on_select
        self._multi = multi

        root = BoxLayout(orientation="vertical", padding=dp(6), spacing=dp(6))
        self.chooser = FileChooserListView(filters=filters or ["*.*"], path="/")
        if multi:
            self.chooser.multiselect = True
        root.add_widget(self.chooser)

        bar = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        cancel = Button(text="取消", background_color=T.GRAY)
        cancel.bind(on_release=self.dismiss)
        ok = Button(text="确定", background_color=T.OR)
        ok.bind(on_release=self._ok)
        bar.add_widget(cancel)
        bar.add_widget(ok)
        root.add_widget(bar)
        self.add_widget(root)

    def _ok(self, *_):
        sel = self.chooser.selection
        if sel and self._on_select:
            self._on_select(sel)
        self.dismiss()


# ============== 参数控件 ==============
class ParamRow(BoxLayout):
    """一行参数: label + 控件"""
    def __init__(self, p, on_change=None, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, spacing=dp(2), **kw)
        self.param = p
        self._on_change = on_change

        lab = Label(text=p.label, size_hint_y=None, height=dp(20), font_size="11sp",
                    halign="left", valign="middle", color=T.INK)
        lab.bind(size=lambda w, _: setattr(w, "text_size", (w.width, w.height)))
        self.add_widget(lab)

        body = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        w = self._build_widget()
        body.add_widget(w)
        self.add_widget(body)
        self.height = dp(60)

    def _build_widget(self):
        p = self.param
        if p.kind == "select":
            sp = Spinner(text=p.options[0][1] if p.options else "",
                         values=[o[1] for o in p.options],
                         background_color=T.OR, color=T.INK)
            # 记录值到 _selected_value
            self._selected_value = p.default
            sp._opts = dict((o[1], o[0]) for o in p.options)
            # 默认显示
            for lbl, val in p.options:
                if val == p.default:
                    sp.text = lbl
                    break

            def _on_text(sp, text):
                self._selected_value = sp._opts.get(text, text)
                if self._on_change:
                    self._on_change(self.param.key, self._selected_value)
            sp.bind(text=_on_text)
            self._widget = sp
            return sp

        if p.kind == "slider":
            box = BoxLayout(spacing=dp(6))
            sl = Slider(min=p.min, max=p.max, value=p.default, step=p.step if p.step else 1)
            disp = Label(text=f"{p.default:g}{p.suffix}", size_hint_x=None, width=dp(80),
                         color=T.INDIGO, bold=True)
            sl.bind(value=lambda w, v, d=disp: setattr(d, "text", f"{v:g}{p.suffix}"))
            box.add_widget(sl)
            box.add_widget(disp)
            self._widget = sl
            self._slider = sl
            return box

        if p.kind == "number":
            ti = TextInput(text=str(p.default), input_filter="float", multiline=False,
                           background_color=(1, 1, 1, 1), foreground_color=T.INK, padding=(dp(6), dp(8)))
            self._widget = ti
            return ti

        if p.kind == "checkbox":
            tb = ToggleButton(text=p.label, state="down" if p.default else "normal",
                              background_color=T.OR if p.default else T.GRAY_L,
                              color=T.INK)
            self._widget = tb
            return tb

        if p.kind in ("text", "textarea"):
            ti = TextInput(text=str(p.default or ""), multiline=(p.kind == "textarea"),
                           background_color=(1, 1, 1, 1), foreground_color=T.INK, padding=(dp(6), dp(8)))
            if p.kind == "textarea":
                ti.size_hint_y = None
                ti.height = dp(120)
            self._widget = ti
            return ti

        if p.kind == "file":
            box = BoxLayout(spacing=dp(4))
            ti = TextInput(text=str(p.default or ""), multiline=False,
                           background_color=(1, 1, 1, 1), foreground_color=T.INK, padding=(dp(6), dp(8)))
            btn = Button(text="📁 浏览", size_hint_x=None, width=dp(80), background_color=T.OR)
            btn.bind(on_release=lambda *_: self._pick_file(p.placeholder or "所有文件 (*.*)"))
            box.add_widget(ti)
            box.add_widget(btn)
            self._widget = ti
            self._picker_filt = p.placeholder or "所有文件 (*.*)"
            return box

        # 默认
        ti = TextInput(text=str(p.default or ""), multiline=False)
        self._widget = ti
        return ti

    def _pick_file(self, filt):
        def _on_pick(paths):
            self._widget.text = paths[0] if paths else ""
            if self._on_change:
                self._on_change(self.param.key, paths[0] if paths else "")
        fp = FilePickerPopup(title="选择文件", filters=[filt] if filt else None, on_select=_on_pick)
        fp.open()

    def value(self):
        """返回当前参数值"""
        p = self.param
        w = self._widget
        if p.kind == "select":
            return self._selected_value
        if p.kind == "slider":
            return self._slider.value
        if p.kind == "number":
            try:
                return float(w.text) if "." in w.text else int(w.text)
            except Exception:
                return p.default
        if p.kind == "checkbox":
            return w.state == "down"
        if p.kind in ("text", "textarea", "file"):
            return w.text
        return w.text if hasattr(w, "text") else ""


# ============== 进度条 + 日志 ==============
class ProgressLogBox(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(180),
                         padding=dp(6), spacing=dp(4), **kw)
        with self.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(*T.PAPER)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
        self.bind(pos=self._upd, size=self._upd)

        self.progress = ProgressBar(max=100, value=0, size_hint_y=None, height=dp(8))
        self.add_widget(self.progress)

        self.status = Label(text="待命", size_hint_y=None, height=dp(22), font_size="11sp",
                            color=T.INDIGO, halign="left", valign="middle")
        self.status.bind(size=lambda w, _: setattr(w, "text_size", (w.width, w.height)))
        self.add_widget(self.status)

        self.log = TextInput(text="", readonly=True, background_color=(0.97, 0.94, 0.86, 0.4),
                             foreground_color=T.INK, font_size="10sp")
        self.add_widget(self.log)

    def _upd(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def set_progress(self, v):
        self.progress.value = max(0, min(100, v))

    def set_status(self, txt):
        self.status.text = txt

    def append_log(self, line):
        self.log.text += line + "\n"
        # 滚动到底
        from kivy.core.window import Window
        Clock.schedule_once(lambda *_: setattr(self.log, "cursor", (0, len(self.log.text))), 0.05)
