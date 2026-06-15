"""工具注册表 - Kivy 版精简 12 工具
复用 app.core.tools 中的实现
"""
from __future__ import annotations
from typing import List
from dataclasses import dataclass

from app.core.tools import (
    CompressTool, FormatTool, TrimTool, CutHeadTailTool,
    SplitAutoTool, ToGifTool, ConcatTool, ExtractAudioTool,
    AudioMergeTool, CodecTool, RotateTool, TTSTool,
)


@dataclass
class ToolCard:
    id: str
    name: str
    desc: str
    category: str
    icon: str
    color: tuple
    tool: object


def all_tools() -> List[ToolCard]:
    items = [
        ToolCard("compress", "视频压缩", "多档位压缩 · 体积立减", "视频处理", "📦", (0.78, 0.23, 0.23, 1), CompressTool()),
        ToolCard("format", "格式转换", "MP4 / MOV / MKV / WebM 互转", "视频处理", "🔄", (0.78, 0.23, 0.23, 1), FormatTool()),
        ToolCard("trim", "时长裁剪", "起止时间精确裁剪", "视频处理", "✂️", (0.78, 0.23, 0.23, 1), TrimTool()),
        ToolCard("cut_head_tail", "去头尾", "一键去除片头片尾", "视频处理", "🚮", (0.78, 0.23, 0.23, 1), CutHeadTailTool()),
        ToolCard("split_auto", "自动分割", "按静音/场景自动切段", "视频处理", "🔪", (0.78, 0.23, 0.23, 1), SplitAutoTool()),
        ToolCard("to_gif", "视频转GIF", "自定义帧率/分辨率", "视频处理", "🌀", (0.78, 0.23, 0.23, 1), ToGifTool()),
        ToolCard("concat", "视频拼接", "多段视频顺序拼接", "视频处理", "🎬", (0.78, 0.23, 0.23, 1), ConcatTool()),
        ToolCard("extract_audio", "音频提取", "从视频无损抽取音频", "视频处理", "🎵", (0.78, 0.23, 0.23, 1), ExtractAudioTool()),
        ToolCard("codec", "编码转换", "H.264 / H.265 / VP9 / AV1", "视频处理", "🧬", (0.78, 0.23, 0.23, 1), CodecTool()),
        ToolCard("rotate", "视频旋转", "90° / 180° / 270°", "视频处理", "�", (0.78, 0.23, 0.23, 1), RotateTool()),
        ToolCard("audio_merge", "音频合并", "多段音频顺序拼接", "音频处理", "🎶", (0.16, 0.55, 0.45, 1), AudioMergeTool()),
        ToolCard("tts", "文字转语音", "云端多角色 · 同步 LRC 歌词", "音频处理", "🗣", (0.16, 0.55, 0.45, 1), TTSTool()),
    ]
    return items


def find_tool(tid: str):
    for t in all_tools():
        if t.id == tid:
            return t
    return None
