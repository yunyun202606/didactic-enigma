"""主屏 - 工具卡片网格"""
from __future__ import annotations
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivy.clock import Clock

from app.ui import theming as T
from app.ui.registry import all_tools
from app.ui.widgets import ToolCardView


class MainScreen(BoxLayout):
    def __init__(self, app, **kw):
        super().__init__(orientation="vertical", **kw)
        self.app = app
        self._build_ui()

    def _build_ui(self):
        # 顶部
        with self.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*T.PAPER)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd_bg, size=self._upd_bg)

        # 标题栏
        head = BoxLayout(size_hint_y=None, height=dp(56), padding=(dp(16), dp(8)),
                         spacing=dp(8))
        with head.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(*T.INDIGO)
            self._head_rect = RoundedRectangle(pos=head.pos, size=head.size, radius=[0])
        head.bind(pos=lambda w, *_: setattr(self._head_rect, "pos", w.pos),
                  size=lambda w, *_: setattr(self._head_rect, "size", w.size))

        title = Label(text="流光璃韵 · 视频音频工具", font_size="18sp", bold=True,
                      color=(1, 1, 1, 1), halign="left", valign="middle")
        title.bind(size=lambda w, _: setattr(w, "text_size", (w.width, w.height)))
        head.add_widget(title)
        self.add_widget(head)

        # 滚动卡片网格
        scroll = ScrollView()
        grid = GridLayout(cols=2, spacing=dp(10), padding=dp(12), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        for card in all_tools():
            grid.add_widget(ToolCardView(card, on_tap=self._open))
        scroll.add_widget(grid)
        self.add_widget(scroll)

    def _upd_bg(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _open(self, card):
        self.app.open_tool(card)
