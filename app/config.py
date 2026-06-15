"""应用配置 - 流光璃韵
色彩基调: 朱红·石青·明黄·青绿·宝蓝
材质: 液态玻璃 + 琉璃质感 + 国风窗花
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ==========================================================
# 品牌
# ==========================================================
APP_NAME = "流光璃韵"
APP_SUBTITLE = "全能音视频编辑器"
APP_TAGLINE = "匠心淬炼 · 视听新韵"
APP_VERSION = "0.2.0"
ORG_NAME = "LiuGuangLiYun"

# ==========================================================
# 五行五色 - 主题主色调
# ==========================================================
# 主色 (Traditional Chinese five colors)
ZHU_HONG = "#C53A3A"      # 朱红 - 火位 / 功能操作
SHI_QING = "#4A90E2"      # 石青 - 水位 / 视频处理区
MING_HUANG = "#F5A623"    # 明黄 - 土位 / 重要
QING_LV = "#2E8B57"       # 青绿 - 木位 / 音频处理
BAO_LAN = "#1A237E"       # 宝蓝 - 金位 / 框架

# 兼容旧名
ZHU = ZHU_HONG
HUANG = MING_HUANG
QING = QING_LV
TIAN = SHI_QING
DIAN = BAO_LAN

# 辅助色
LIU_LI = "#FFFFFF80"      # 琉璃白 (半透明)
MO_HEI = "#2C2C2C"        # 墨黑
JIN = "#D4AF37"           # 金
XUAN_ZHI = "#F5EFE0"      # 宣纸米
XUAN_DARK = "#E8D8B5"
YAN_ZHI = "#9C1A1A"       # 绛红 (错误)
ZHU_QING = "#55A44E"      # 竹青 (成功)
HU_PO = "#FF8C00"         # 琥珀 (进行中)
HUI = "#888888"           # 灰 (禁用)

# 状态色
SUCCESS = ZHU_QING
ERROR = YAN_ZHI
PROGRESS = HU_PO
DISABLED = HUI

# ==========================================================
# 路径
# ==========================================================
def app_dir() -> Path:
    base = Path(os.path.expanduser("~")) / ".liuguangliyun"
    base.mkdir(parents=True, exist_ok=True)
    return base


def output_dir() -> Path:
    if os.name == "nt":
        docs = Path(os.path.expanduser("~")) / "Documents"
    else:
        docs = Path(os.path.expanduser("~"))
    out = docs / "流光璃韵" / "输出"
    out.mkdir(parents=True, exist_ok=True)
    return out


# ==========================================================
# FFmpeg
# ==========================================================
FFMPEG_AUTO_DOWNLOAD = True
FFMPEG_VERSION = "6.1.1"
# 使用 gyan.dev 的 essentials 构建 (~30MB, 下载快, 含常用编解码器)
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


# ==========================================================
# 工具分组 (按设计文档的四组分类)
# ==========================================================
TOOL_GROUPS = [
    {
        "id": "basic",
        "name": "基础处理",
        "subtitle": "蓝绿清雅",
        "color": SHI_QING,
        "tools": ["compress", "format", "extract_audio"],
    },
    {
        "id": "edit",
        "name": "编辑裁剪",
        "subtitle": "红黄热烈",
        "color": ZHU_HONG,
        "tools": ["trim", "crop", "rotate", "reverse", "cut_head_tail", "concat"],
    },
    {
        "id": "advanced",
        "name": "高级功能",
        "subtitle": "青蓝深邃",
        "color": BAO_LAN,
        "tools": ["split_manual", "split_auto", "speed", "codec", "denoise", "repair"],
    },
    {
        "id": "special",
        "name": "特殊转换",
        "subtitle": "多彩斑斓",
        "color": MING_HUANG,
        "tools": ["to_gif", "gif_to_video", "tts", "m3u8", "audio_merge", "fix_duration", "subtitle"],
    },
]

# 侧边栏四大主类
MAIN_CATEGORIES = [
    {"id": "file",   "name": "文件管理", "icon": "📁", "color": SHI_QING},
    {"id": "video",  "name": "视频处理", "icon": "🎬", "color": ZHU_HONG},
    {"id": "audio",  "name": "音频处理", "icon": "🎵", "color": QING_LV},
    {"id": "tool",   "name": "高级工具", "icon": "🔧", "color": BAO_LAN},
    {"id": "setting","name": "设置中心", "icon": "⚙️", "color": MING_HUANG},
]
