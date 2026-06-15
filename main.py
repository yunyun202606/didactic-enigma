"""流光璃韵 · Android 入口
用法:
  桌面: python main.py
  Android: buildozer android debug deploy
"""
import os, sys

# 桌面开发时把 kivy_app 加进 path, Android 端 buildozer 会自动处理
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.app import LiuguangApp

if __name__ == "__main__":
    LiuguangApp().run()
