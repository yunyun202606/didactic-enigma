"""Kivy App - 流光璃韵 Android 版"""
from __future__ import annotations
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.utils import platform

from app.ui.main_screen import MainScreen
from app.ui.tool_screen import ToolScreen


class MainScreen_(Screen):
    pass


class ToolScreen_(Screen):
    pass


class LiuguangApp(App):
    def build(self):
        self.title = "流光璃韵"
        self.sm = ScreenManager()
        self._main = MainScreen_(name="main")
        self._main.add_widget(MainScreen(app=self))
        self.sm.add_widget(self._main)
        return self.sm

    def open_tool(self, card):
        ts = ToolScreen_(name=f"tool_{card.id}")
        ts.add_widget(ToolScreen(app=self, card=card))
        self.sm.add_widget(ts)
        self.sm.current = ts.name

    def goto_main(self):
        # 移除所有工具屏
        for child in list(self.sm.children):
            if child.name.startswith("tool_"):
                self.sm.remove_widget(child)
        self.sm.current = "main"


if __name__ == "__main__":
    LiuguangApp().run()
