"""22 项工具定义 - 流光璃韵"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any


# ============================================================
# Param 元数据
# ============================================================
@dataclass
class Param:
    key: str
    label: str
    kind: str  # number / slider / select / checkbox / text / textarea
    default: Any = None
    suffix: str = ""
    min: float = 0
    max: float = 100
    step: float = 1
    options: List[Tuple[Any, str]] = field(default_factory=list)
    placeholder: str = ""


@dataclass
class Tool:
    id: str
    name: str
    desc: str
    category: str
    icon: str
    color: str
    input_kind: str  # video / audio / image / multi_video / multi_audio / url / text / none
    output_ext: str
    params: List[Param] = field(default_factory=list)

    def build_args(self, params: Dict[str, Any], inputs: List[Path], output: Path) -> List[str]:
        """由子类实现, 返回不包含 -i 的参数 (最后包含 output 路径)"""
        raise NotImplementedError


# ============================================================
# 工具实现
# ============================================================
class CompressTool(Tool):
    # 档位预设: 用户选择档位时, 自动覆盖 codec/preset/quality, 避免用户不知调哪个参数
    PRESETS = {
        "extreme":  ("libx265", "veryslow", 38, "极致压缩 (H.265 · 极慢 · 体积最小)"),
        "high":     ("libx265", "slow",     32, "高压缩 (H.265 · 慢速)"),
        "balanced": ("libx264", "slow",     28, "平衡 (H.264 · 慢速 · 推荐)"),
        "fast":     ("libx264", "fast",     24, "快速 (H.264 · 较快)"),
        "size":     ("libx265", "veryslow", 35, "目标大小 (H.265 · 按目标大小计算码率)"),
        "custom":   (None, None, None,        "自定义 - 使用下方参数"),
    }

    def __init__(self):
        super().__init__(
            id="compress", name="视频压缩", desc="多档位压缩 · 一键立减体积",
            category="视频处理", icon="📦", color="#C53A3A",
            input_kind="video", output_ext="mp4",
            params=[
                Param("preset", "压缩档位", "select", default="extreme", options=[
                    ("extreme",   "极致压缩 (H.265 · 极慢 · 体积最小 · 推荐)"),
                    ("high",      "高压缩 (H.265 · 慢速)"),
                    ("balanced",  "平衡 (H.264 · 慢速)"),
                    ("fast",      "快速 (H.264 · 较快)"),
                    ("size",      "目标大小 (按 MB 限制自动算码率)"),
                    ("custom",    "自定义 - 使用下方参数"),
                ]),
                Param("mode", "编码模式 (自定义)", "select", default="quality", options=[
                    ("quality", "质量模式 (CRF)"),
                    ("bitrate", "码率模式 (固定)"),
                ]),
                Param("quality", "压缩质量 (CRF, 越高=越小)", "slider",
                      default=32, min=18, max=40, step=1, suffix=""),
                Param("bitrate", "目标视频码率 (码率模式)", "number", default=800, suffix="kbps", min=100, max=20000),
                Param("target_mb", "目标文件大小 MB (size 档位)", "number", default=10, suffix="MB", min=1, max=2000),
                Param("audio_bitrate", "音频码率", "number", default=64, suffix="kbps", min=32, max=320),
                Param("width", "宽度 (-1=保持)", "number", default=-1, min=-2, max=7680),
                Param("height", "高度 (-1=保持)", "number", default=-1, min=-2, max=4320),
                Param("codec", "视频编码 (自定义)", "select", default="libx264", options=[
                    ("libx264", "H.264 (libx264) - 通用兼容"),
                    ("libx265", "H.265 (libx265) - 体积减半"),
                    ("libvpx-vp9", "VP9 - 开源 Web"),
                    ("libaom-av1", "AV1 - 最新, 极小"),
                    ("mpeg4", "MPEG-4 - 老设备兼容"),
                ]),
                Param("preset_speed", "压缩速度 (自定义)", "select", default="veryslow", options=[
                    ("ultrafast", "极快 (低压缩)"),
                    ("fast", "快速"),
                    ("medium", "平衡"),
                    ("slow", "慢速"),
                    ("veryslow", "极慢 (最高压缩)"),
                ]),
            ],
        )

    def build_args(self, p, inputs, output):
        # 1. 先用档位预设覆盖 codec/preset/quality
        preset_key = p.get("preset") or "balanced"
        if preset_key in self.PRESETS and preset_key != "custom":
            pcodec, ppreset, pcrf, _ = self.PRESETS[preset_key]
            if pcodec: p["codec"] = pcodec
            if ppreset: p["preset_speed"] = ppreset
            if pcrf is not None: p["quality"] = pcrf

        args = []
        vf = []
        w = p.get("width")
        h = p.get("height")
        if w is not None and w not in (-1, 0):
            vf.append(f"scale={w}:-2")
        elif h is not None and h not in (-1, 0):
            vf.append(f"scale=-2:{h}")
        if vf:
            args += ["-vf", ",".join(vf)]

        codec = p.get("codec") or "libx264"
        preset = p.get("preset_speed") or "slow"
        ab = p.get("audio_bitrate") or 64
        mode = p.get("mode") or "quality"

        # 2. size 档位: 根据目标 MB 反算视频码率
        if preset_key == "size":
            try:
                target_mb = float(p.get("target_mb") or 10)
                # 探测源时长
                src = inputs[0] if inputs else None
                duration = self._probe_duration(src) if src else None
                if duration and duration > 0:
                    # 总码率 (kbps) = (MB * 8 * 1024) / 秒
                    total_kbps = (target_mb * 8 * 1024) / duration
                    video_kbps = max(100, int(total_kbps - ab))
                    args += ["-c:v", codec, "-b:v", f"{video_kbps}k",
                             "-maxrate", f"{int(video_kbps * 1.2)}k",
                             "-bufsize", f"{video_kbps * 2}k",
                             "-preset", preset,
                             "-c:a", "aac", "-b:a", f"{ab}k",
                             "-movflags", "+faststart",
                             str(output)]
                    return args
            except Exception:
                pass  # 探测失败则回落到 CRF

        if mode == "quality":
            # 质量模式: 用 CRF, 自动让编码器决定码率, 压缩效率最高
            crf = int(p.get("quality") or 32)
            # 不同编码器的 CRF 等价范围略有不同, 这里做轻量调整
            if codec == "libx265":
                crf = max(0, crf - 3)  # H.265 同等画质 CRF 约低 3-4
            elif codec == "libaom-av1":
                crf = max(0, crf - 6)
            args += ["-c:v", codec, "-crf", str(crf), "-preset", preset,
                     "-c:a", "aac", "-b:a", f"{ab}k",
                     "-movflags", "+faststart",
                     str(output)]
        else:
            # 码率模式: 用 -b:v + -maxrate + -bufsize 真正封顶码率
            vb = p.get("bitrate") or 800
            args += ["-c:v", codec, "-b:v", f"{vb}k",
                     "-maxrate", f"{int(vb * 1.2)}k",
                     "-bufsize", f"{vb * 2}k",
                     "-preset", preset,
                     "-c:a", "aac", "-b:a", f"{ab}k",
                     "-movflags", "+faststart",
                     str(output)]
        return args

    @staticmethod
    def _probe_duration(src_path) -> Optional[float]:
        """探测视频时长(秒). 优先 ffprobe, 失败则用 ffmpeg -i 解析"""
        if not src_path:
            return None
        # 1) 尝试 ffprobe
        try:
            from .ffmpeg import get_ffprobe_path, get_ffmpeg_path
            import subprocess, re
            probe = get_ffprobe_path()
            if probe:
                out = subprocess.run(
                    [probe, "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(src_path)],
                    capture_output=True, text=True, timeout=10
                )
                v = out.stdout.strip()
                if v:
                    return float(v)
        except Exception:
            pass
        # 2) 回落到 ffmpeg -i (从 stderr 解析 Duration)
        try:
            ffm = get_ffmpeg_path()
            out = subprocess.run(
                [ffm, "-i", str(src_path)],
                capture_output=True, text=True, timeout=10
            )
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", out.stderr)
            if m:
                h, mi, s = m.groups()
                return int(h) * 3600 + int(mi) * 60 + float(s)
        except Exception:
            pass
        return None


class FormatTool(Tool):
    def __init__(self):
        super().__init__(
            id="format", name="格式转换", desc="MP4 / MOV / MKV / WebM 互转",
            category="视频处理", icon="🔄", color="#C53A3A",
            input_kind="video", output_ext="mp4",
            params=[
                Param("format", "输出格式", "select", default="mp4", options=[
                    ("mp4", "MP4"),
                    ("mov", "MOV"),
                    ("mkv", "MKV"),
                    ("webm", "WebM"),
                    ("avi", "AVI"),
                    ("flv", "FLV"),
                    ("ts", "TS"),
                    ("gif", "GIF"),
                ]),
                Param("codec", "视频编码", "select", default="libx264", options=[
                    ("libx264", "H.264"),
                    ("libx265", "H.265"),
                    ("copy", "不重编码 (极速)"),
                ]),
                Param("crf", "质量 (CRF)", "slider", default=23, min=0, max=51, step=1, suffix=""),
            ],
        )

    def build_args(self, p, inputs, output):
        fmt = p.get("format") or "mp4"
        codec = p.get("codec") or "libx264"
        crf = p.get("crf", 23)
        args = ["-c:v", codec, "-crf", str(int(crf))]
        if fmt in ("mp4", "mov", "ts"):
            args += ["-c:a", "aac", "-movflags", "+faststart"]
        elif fmt == "webm":
            args += ["-c:a", "libvorbis"]
        out = str(output).rsplit(".", 1)[0] + "." + fmt
        args += [out]
        return args


class TrimTool(Tool):
    def __init__(self):
        super().__init__(
            id="trim", name="时长裁剪", desc="起止时间精确裁剪",
            category="视频处理", icon="✂️", color="#C53A3A",
            input_kind="video", output_ext="mp4",
            params=[
                Param("start", "开始时间 (秒)", "number", default=0, min=0, max=99999),
                Param("duration", "持续时长 (秒, 0=到结尾)", "number", default=0, min=0, max=99999),
            ],
        )

    def build_args(self, p, inputs, output):
        args = ["-ss", str(p.get("start") or 0)]
        dur = p.get("duration") or 0
        if dur > 0:
            args += ["-t", str(dur)]
        args += ["-c", "copy", "-avoid_negative_ts", "make_zero", str(output)]
        return args


class CropTool(Tool):
    def __init__(self):
        super().__init__(
            id="crop", name="画面裁剪", desc="自定义裁剪区域",
            category="视频处理", icon="🖼️", color="#C53A3A",
            input_kind="video", output_ext="mp4",
            params=[
                Param("width", "输出宽度", "number", default=1280, min=64, max=7680),
                Param("height", "输出高度", "number", default=720, min=64, max=4320),
                Param("x", "X 偏移", "number", default=0, min=0, max=7680),
                Param("y", "Y 偏移", "number", default=0, min=0, max=4320),
            ],
        )

    def build_args(self, p, inputs, output):
        args = ["-vf", f"crop={p.get('width') or 1280}:{p.get('height') or 720}:{p.get('x') or 0}:{p.get('y') or 0}",
                "-c:a", "copy", str(output)]
        return args


class SplitManualTool(Tool):
    def __init__(self):
        super().__init__(
            id="split_manual", name="手动分割", desc="按时间段切出多段",
            category="视频处理", icon="🔪", color="#1A237E",
            input_kind="video", output_ext="mp4",
            params=[
                Param("segments", "时间段 (秒, 逗号分隔, 如 0,30,60,90)", "text", default="0,30,60"),
            ],
        )

    def build_args(self, p, inputs, output):
        # 手动分割: 由 tool_page 按多段切出, 此处仅返回标记
        return ["__split_manual__", str(p.get("segments", "0,30,60")), str(output)]


class SplitAutoTool(Tool):
    def __init__(self):
        super().__init__(
            id="split_auto", name="自动分割", desc="按静音/场景自动切段",
            category="视频处理", icon="✨", color="#1A237E",
            input_kind="video", output_ext="mp4",
            params=[
                Param("threshold", "静音阈值 (dB)", "slider", default=-30, min=-60, max=0, step=1, suffix=" dB"),
                Param("min_duration", "最短段长 (秒)", "number", default=2, suffix="s", min=1, max=60),
            ],
        )

    def build_args(self, p, inputs, output):
        # 自动分割: 由 tool_page 用 silencedetect 找到静音点, 再切分
        return ["__split_auto__", str(p.get("threshold", -30)), str(p.get("min_duration", 2)), str(output)]


class ToGifTool(Tool):
    def __init__(self):
        super().__init__(
            id="to_gif", name="视频转 GIF", desc="自定义帧率/分辨率",
            category="视频处理", icon="🎞️", color="#F5A623",
            input_kind="video", output_ext="gif",
            params=[
                Param("fps", "帧率", "number", default=15, min=5, max=60, suffix="fps"),
                Param("width", "宽度", "number", default=480, min=64, max=1920),
                Param("start", "起始 (秒)", "number", default=0, min=0),
                Param("duration", "时长 (秒)", "number", default=5, min=1, max=60),
            ],
        )

    def build_args(self, p, inputs, output):
        return [
            "-ss", str(p.get("start") or 0),
            "-t", str(p.get("duration") or 5),
            "-vf", f"fps={p.get('fps') or 15},scale={p.get('width') or 480}:-1:flags=lanczos",
            "-loop", "0", str(output)
        ]


class GifToVideoTool(Tool):
    def __init__(self):
        super().__init__(
            id="gif_to_video", name="GIF 转视频", desc="GIF 转为 MP4/WebM",
            category="视频处理", icon="📽️", color="#F5A623",
            input_kind="image", output_ext="mp4",
            params=[
                Param("format", "输出格式", "select", default="mp4", options=[
                    ("mp4", "MP4"), ("webm", "WebM"), ("mov", "MOV"),
                ]),
            ],
        )

    def build_args(self, p, inputs, output):
        out_fmt = p.get("format") or "mp4"
        out = str(output).rsplit(".", 1)[0] + "." + out_fmt
        if out_fmt == "webm":
            return ["-c:v", "libvpx-vp9", "-pix_fmt", "yuv420p", out]
        return ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]


class AudioMergeTool(Tool):
    def __init__(self):
        super().__init__(
            id="audio_merge", name="音频合并", desc="多音频顺序拼接",
            category="音频处理", icon="🎵", color="#2E8B57",
            input_kind="multi_audio", output_ext="mp3",
            params=[
                Param("format", "输出格式", "select", default="mp3", options=[
                    ("mp3", "MP3"), ("aac", "AAC"), ("wav", "WAV"), ("flac", "FLAC"), ("ogg", "OGG"),
                ]),
            ],
        )

    def build_args(self, p, inputs, output):
        fmt = (p.get("format") or "mp3").lower()
        if fmt == "mp3":
            codec = ["-c:a", "libmp3lame", "-b:a", "192k"]
        elif fmt == "aac":
            codec = ["-c:a", "aac", "-b:a", "192k"]
        elif fmt == "wav":
            codec = ["-c:a", "pcm_s16le"]
        elif fmt == "flac":
            codec = ["-c:a", "flac"]
        else:
            codec = ["-c:a", "libvorbis", "-b:a", "192k"]
        return codec + [str(output)]


class SpeedTool(Tool):
    def __init__(self):
        super().__init__(
            id="speed", name="视频变速", desc="0.25x – 4x 无损变速",
            category="视频处理", icon="⏩", color="#1A237E",
            input_kind="video", output_ext="mp4",
            params=[
                Param("speed", "变速倍率", "slider", default=1.0, min=0.25, max=4.0, step=0.05, suffix="x"),
            ],
        )

    def build_args(self, p, inputs, output):
        s = float(p.get("speed") or 1.0)
        # setpts=PTS/SPEED, atempo=SPEED
        video_filter = f"setpts=PTS/{s}"
        audio_filter = f"atempo={s}" if 0.5 <= s <= 2.0 else f"atempo={min(s,2.0)},atempo={s/min(s,2.0)}"
        return [
            "-vf", video_filter, "-af", audio_filter,
            "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", str(output)
        ]


class CodecTool(Tool):
    def __init__(self):
        super().__init__(
            id="codec", name="编码转换", desc="H.264 / H.265 / VP9 / AV1 互转",
            category="视频处理", icon="⚙️", color="#1A237E",
            input_kind="video", output_ext="mp4",
            params=[
                Param("vcodec", "目标视频编码", "select", default="libx265", options=[
                    ("libx264", "H.264 - 通用"),
                    ("libx265", "H.265 - 体积更小"),
                    ("libvpx-vp9", "VP9 - Web"),
                    ("libaom-av1", "AV1 - 新一代"),
                ]),
                Param("acodec", "目标音频编码", "select", default="aac", options=[
                    ("aac", "AAC"), ("libmp3lame", "MP3"),
                    ("libvorbis", "Vorbis"), ("copy", "不重编码"),
                ]),
                Param("crf", "质量 CRF", "slider", default=23, min=0, max=51, step=1, suffix=""),
            ],
        )

    def build_args(self, p, inputs, output):
        codec = p.get("vcodec") or "libx264"
        acodec = p.get("acodec") or "aac"
        crf = p.get("crf", 23)
        return [
            "-c:v", codec, "-crf", str(int(crf)),
            "-c:a", acodec, "-movflags", "+faststart", str(output)
        ]


class DenoiseTool(Tool):
    def __init__(self):
        super().__init__(
            id="denoise", name="视频降噪", desc="视频+音频双重降噪",
            category="视频处理", icon="🌀", color="#1A237E",
            input_kind="video", output_ext="mp4",
            params=[
                Param("strength", "降噪强度", "slider", default=4, min=1, max=10, step=1, suffix=""),
                Param("audio_nr", "音频降噪", "checkbox", default=True),
            ],
        )

    def build_args(self, p, inputs, output):
        s = int(p.get("strength") or 4)
        vf = f"hqdn3d={s}:{s}:{s}:{s}"
        if p.get("audio_nr", True):
            af = "afftdn=nf=-25"
            return ["-vf", vf, "-af", af, "-c:v", "libx264", "-c:a", "aac", str(output)]
        return ["-vf", vf, "-c:v", "libx264", "-c:a", "copy", str(output)]


class RepairTool(Tool):
    def __init__(self):
        super().__init__(
            id="repair", name="损坏修复", desc="重新封装, 修复文件结构",
            category="视频处理", icon="🛠️", color="#1A237E",
            input_kind="video", output_ext="mp4",
            params=[],
        )

    def build_args(self, p, inputs, output):
        # 重新封装, 重新生成 moov 原子, +faststart 让 mp4 可边下边播
        # 注意: ignore_editlist 与 -c copy 冲突, 单独用 faststart
        return ["-c", "copy", "-movflags", "+faststart", str(output)]


class FixDurationTool(Tool):
    def __init__(self):
        super().__init__(
            id="fix_duration", name="时长修复", desc="重建时长元数据",
            category="视频处理", icon="⏱️", color="#F5A623",
            input_kind="video", output_ext="mp4",
            params=[],
        )

    def build_args(self, p, inputs, output):
        return ["-c", "copy", "-map", "0", "-movflags", "faststart", str(output)]


class RotateTool(Tool):
    def __init__(self):
        super().__init__(
            id="rotate", name="视频旋转", desc="90° / 180° / 270°",
            category="视频处理", icon="🔁", color="#C53A3A",
            input_kind="video", output_ext="mp4",
            params=[
                Param("angle", "旋转角度", "select", default="90", options=[
                    ("90", "顺时针 90°"),
                    ("180", "180°"),
                    ("270", "逆时针 90°"),
                    ("vflip", "垂直翻转"),
                    ("hflip", "水平翻转"),
                ]),
            ],
        )

    def build_args(self, p, inputs, output):
        a = p.get("angle") or "90"
        if a in ("vflip", "hflip"):
            vf = a
        else:
            vf = f"transpose={1 if a == '90' else (2 if a == '180' else 3)}"
        return ["-vf", vf, "-c:a", "copy", str(output)]


class ReverseTool(Tool):
    def __init__(self):
        super().__init__(
            id="reverse", name="视频倒放", desc="时间轴倒放 (含音频)",
            category="视频处理", icon="⏪", color="#C53A3A",
            input_kind="video", output_ext="mp4",
            params=[
                Param("with_audio", "包含音频", "checkbox", default=True),
            ],
        )

    def build_args(self, p, inputs, output):
        args = ["-vf", "reverse"]
        if p.get("with_audio", True):
            args += ["-af", "areverse"]
        args += ["-c:v", "libx264", "-c:a", "aac", str(output)]
        return args


class CutHeadTailTool(Tool):
    def __init__(self):
        super().__init__(
            id="cut_head_tail", name="去头尾", desc="一键去除片头片尾",
            category="视频处理", icon="🚮", color="#C53A3A",
            input_kind="video", output_ext="mp4",
            params=[
                Param("head", "去除片头 (秒)", "number", default=3, min=0, max=999, suffix="s"),
                Param("tail", "去除片尾 (秒)", "number", default=3, min=0, max=999, suffix="s"),
            ],
        )

    def build_args(self, p, inputs, output):
        # head + tail: 由 tool_page 在拿到时长后特判处理, 此处仅返回 head 偏移
        # tail 处理见 _run_cut_head_tail
        return ["__cut_head_tail__", str(p.get("head", 0)), str(p.get("tail", 0)), str(output)]


class ConcatTool(Tool):
    def __init__(self):
        super().__init__(
            id="concat", name="视频拼接", desc="多视频顺序拼接",
            category="视频处理", icon="🧩", color="#C53A3A",
            input_kind="multi_video", output_ext="mp4",
            params=[],
        )

    def build_args(self, p, inputs, output):
        return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k", str(output)]


class ExtractAudioTool(Tool):
    def __init__(self):
        super().__init__(
            id="extract_audio", name="音频提取", desc="从视频中无损抽取音频",
            category="音频处理", icon="🎵", color="#2E8B57",
            input_kind="video", output_ext="mp3",
            params=[
                Param("format", "输出格式", "select", default="mp3", options=[
                    ("mp3", "MP3"), ("aac", "AAC"), ("wav", "WAV"), ("flac", "FLAC"), ("m4a", "M4A"),
                ]),
                Param("bitrate", "码率", "number", default=192, min=32, max=320, suffix="kbps"),
            ],
        )

    def build_args(self, p, inputs, output):
        fmt = p.get("format") or "mp3"
        out = str(output).rsplit(".", 1)[0] + "." + fmt
        codec = {"mp3": "libmp3lame", "aac": "aac", "wav": "pcm_s16le",
                 "flac": "flac", "m4a": "aac"}.get(fmt, "aac")
        return ["-vn", "-c:a", codec, "-b:a", f"{p.get('bitrate') or 192}k", out]


class TTSTool(Tool):
    def __init__(self):
        super().__init__(
            id="tts", name="文字转语音", desc="云端/本机多角色合成 + 同步 LRC 歌词",
            category="音频处理", icon="🗣️", color="#2E8B57",
            input_kind="text", output_ext="wav",
            params=[
                Param("voice", "音色", "select", default="edge:zh-CN-XiaoxiaoNeural", options=[]),
                Param("rate", "语速", "slider", default=1.0, min=0.5, max=2.0, step=0.1, suffix="x"),
                Param("pitch", "音调", "slider", default=1.0, min=0.5, max=2.0, step=0.1, suffix="x"),
                Param("gen_lrc", "同步生成 LRC 歌词", "checkbox", default=True),
            ],
        )

    def build_args(self, p, inputs, output):
        return [str(output)]


class M3U8Tool(Tool):
    def __init__(self):
        super().__init__(
            id="m3u8", name="M3U8 转 MP4", desc="解析 HLS 片段, 合并为 MP4",
            category="格式转换", icon="📜", color="#4A90E2",
            input_kind="url", output_ext="mp4",
            params=[],
        )

    def build_args(self, p, inputs, output):
        return [str(output)]


class SubtitleTool(Tool):
    def __init__(self):
        super().__init__(
            id="subtitle", name="字幕烧录", desc="将 SRT 字幕硬烧入视频",
            category="实用工具", icon="📝", color="#1A237E",
            input_kind="video", output_ext="mp4",
            params=[
                Param("subtitle", "SRT 字幕文件", "file", default="", placeholder="SRT 字幕 (*.srt);;所有文件 (*.*)"),
                Param("font", "字体", "text", default="Microsoft YaHei", placeholder="如 Microsoft YaHei"),
                Param("fontsize", "字号", "number", default=24, min=12, max=72),
            ],
        )

    def build_args(self, p, inputs, output):
        sub = p.get("subtitle", "").strip()
        if not sub:
            raise ValueError("请先选择 SRT 字幕文件")
        if not Path(sub).exists():
            raise ValueError(f"字幕文件不存在: {sub}")
        font = p.get("font", "Microsoft YaHei") or "Microsoft YaHei"
        fs = p.get("fontsize", 24)
        # Windows 路径: 反斜杠转义, 冒号也转义
        sub_escaped = sub.replace("\\", "/").replace(":", "\\:")
        font_escaped = font.replace("\\", "/").replace(":", "\\:")
        vf = f"subtitles='{sub_escaped}':force_style='FontName={font_escaped},FontSize={fs}'"
        return ["-vf", vf, "-c:v", "libx264", "-c:a", "copy", str(output)]


class IDCardOCRTool(Tool):
    def __init__(self):
        super().__init__(
            id="id_card_ocr", name="证件识别", desc="身份证/户口本 图片OCR提取信息",
            category="实用工具", icon="🪪", color="#4A90E2",
            input_kind="image", output_ext="json",
            params=[
                Param("doc_type", "证件类型", "select", default="auto", options=[
                    ("auto", "自动识别"),
                    ("id_card", "身份证"),
                    ("household", "户口本"),
                ]),
                Param("engine", "OCR引擎", "select", default="paddle", options=[
                    ("paddle", "PaddleOCR (推荐, 中文精准)"),
                    ("tesseract", "Tesseract (轻量)"),
                ]),
                Param("save_raw", "保留原始识别文本", "checkbox", default=False),
            ],
        )

    def build_args(self, p, inputs, output):
        return ["__id_card_ocr__",
                str(p.get("doc_type", "auto")),
                str(p.get("engine", "paddle")),
                str(p.get("save_raw", False)),
                str(output)]

    @staticmethod
    def run_ocr(image_path: str, doc_type: str, engine: str,
                save_raw: bool, output_path: str) -> Dict[str, Any]:
        from .id_card_ocr import extract_id_info, save_result
        info = extract_id_info(image_path, doc_type=doc_type, engine=engine)
        if not save_raw and "raw_text" in info:
            del info["raw_text"]
        save_result(info, output_path)
        return info


# ============================================================
# 注册所有工具
# ============================================================
ALL_TOOLS: List[Tool] = [
    CompressTool(),
    FormatTool(),
    TrimTool(),
    CropTool(),
    SplitManualTool(),
    SplitAutoTool(),
    ToGifTool(),
    GifToVideoTool(),
    AudioMergeTool(),
    SpeedTool(),
    CodecTool(),
    DenoiseTool(),
    RepairTool(),
    FixDurationTool(),
    RotateTool(),
    ReverseTool(),
    CutHeadTailTool(),
    ConcatTool(),
    ExtractAudioTool(),
    TTSTool(),
    M3U8Tool(),
    SubtitleTool(),
    IDCardOCRTool(),
]

TOOL_MAP: Dict[str, Tool] = {t.id: t for t in ALL_TOOLS}

# 分类
CATEGORIES = sorted({t.category for t in ALL_TOOLS})
