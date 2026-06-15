"""文字转语音 (TTS) - 真实合成

优先级:
  1. edge-tts (微软云端, 质量高, 男/女/多语言, 首次需联网)
  2. pyttsx3 (Windows SAPI5 离线, 需系统装中文语音)
  3. 占位正弦波 (兜底)
"""
from __future__ import annotations

import asyncio
import math
import re
import struct
import wave
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Callable, List, Tuple


# ============================================================
# 男声 / 女声 列表
# ============================================================
# edge-tts (微软云) - 高质量, 首次需联网
EDGE_VOICES = {
    "female": [
        ("zh-CN-XiaoxiaoNeural", "晓晓 (温柔女声, 推荐)"),
        ("zh-CN-XiaoyiNeural", "晓伊 (活泼女声)"),
        ("zh-CN-XiaomengNeural", "晓梦 (甜美女声)"),
        ("zh-CN-XiaomoNeural", "晓墨 (成熟女声)"),
        ("zh-CN-XiaoqianNeural", "晓倩 (新闻女声)"),
        ("zh-CN-XiaoruiNeural", "晓睿 (智慧女声)"),
        ("zh-CN-XiaoxuanNeural", "晓萱 (文艺女声)"),
    ],
    "male": [
        ("zh-CN-YunxiNeural", "云希 (阳光男声, 推荐)"),
        ("zh-CN-YunyangNeural", "云扬 (专业男声)"),
        ("zh-CN-YunjianNeural", "云健 (浑厚男声)"),
        ("zh-CN-YunfengNeural", "云枫 (磁性男声)"),
        ("zh-CN-YunhaoNeural", "云皓 (新闻男声)"),
        ("zh-CN-YunzeNeural", "云泽 (少年男声)"),
    ],
    "child": [
        ("zh-CN-YunxiNeural", "云希 (少年音)"),
    ],
}

# Windows SAPI5 (离线) - 自动从系统读取
def _list_sapi_voices() -> List[Tuple[str, str, str]]:
    """返回 [(voice_id, display_name, gender)]"""
    voices: List[Tuple[str, str, str]] = []
    try:
        import win32com.client  # type: ignore
        try:
            sp = win32com.client.Dispatch("SAPI.SpVoice")
            cat = sp.GetVoices()
            for i in range(cat.Count):
                v = cat.Item(i)
                vid = v.GetAttribute("ID")
                desc = v.GetDescription()
                gender = v.GetAttribute("Gender")  # 0=中性 1=女 2=男
                gender_s = "female" if gender == "1" else ("male" if gender == "2" else "child")
                voices.append((vid, desc, gender_s))
        except Exception:
            pass
    except Exception:
        pass
    return voices


def list_voices() -> List[dict]:
    """返回 UI 用的语音选项"""
    result = []
    has_edge = _has_edge_tts()
    if has_edge:
        for gender, items in EDGE_VOICES.items():
            for vid, label in items:
                if gender == "female":
                    result.append({"id": f"edge:{vid}", "label": f"☁ {label}", "gender": gender, "engine": "edge"})
                elif gender == "male":
                    result.append({"id": f"edge:{vid}", "label": f"☁ {label}", "gender": gender, "engine": "edge"})
    # SAPI5
    sapi = _list_sapi_voices()
    for vid, desc, gender in sapi:
        result.append({"id": f"sapi:{vid}", "label": f"🖥 {desc} (本机)", "gender": gender, "engine": "sapi"})
    if not result:
        result.append({"id": "sine", "label": "🎵 占位音 (无 TTS 可用)", "gender": "female", "engine": "sine"})
    return result


def _has_edge_tts() -> bool:
    try:
        import edge_tts  # type: ignore
        return True
    except Exception:
        return False


def _has_sapi() -> bool:
    try:
        import win32com.client  # type: ignore
        return True
    except Exception:
        return False


# ============================================================
# 主入口
# ============================================================
def tts_to_wav(
    text: str,
    output: Path,
    voice_id: str = "edge:zh-CN-XiaoxiaoNeural",
    rate: float = 1.0,
    pitch: float = 1.0,
    output_lrc: Optional[Path] = None,
    on_log: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[float, str], None]] = None,
) -> Path:
    """合成语音到 WAV, 可选同时生成 LRC 歌词

    voice_id: 形如 "edge:zh-CN-XiaoxiaoNeural" / "sapi:MSTTS_V110_zhCN_HuihuiM" / "sine"
    on_progress: 回调 (0..1, 阶段说明)
    """
    log = on_log or (lambda m: None)
    prog = on_progress or (lambda p, m: None)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    engine, _, vid = voice_id.partition(":")

    if engine == "edge" and _has_edge_tts():
        return _tts_edge(text, output, vid, rate, pitch, output_lrc, log, prog)
    if engine == "sapi" and _has_sapi():
        return _tts_sapi(text, output, vid, rate, pitch, output_lrc, log, prog)
    # 兜底: edge 不可用, 尝试 sapi
    if engine == "edge" and _has_sapi():
        log("[提示] edge-tts 未安装, 改用本机 SAPI5")
        return _tts_sapi_first(text, output, rate, pitch, output_lrc, log, prog)
    # 最后: 正弦波
    log("[提示] 未找到 TTS 引擎, 使用占位音")
    return _tts_sine(text, output, rate, pitch, output_lrc, log, prog)


# ============================================================
# edge-tts (微软云)
# ============================================================
def _test_edge_connectivity(log) -> bool:
    """快速测试能否连上微软 TTS 服务

    直接尝试一次最小合成, 比 HTTP 探测更准确。
    """
    try:
        import edge_tts
        import asyncio
        async def _probe():
            comm = edge_tts.Communicate("测", voice="zh-CN-XiaoxiaoNeural")
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    return True
                if chunk["type"] == "error":
                    return False
            return True
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_probe())
        finally:
            loop.close()
    except Exception as e:
        log(f"[提示] 连通性测试异常: {type(e).__name__}: {e}")
        return False


def _tts_edge(text, output, voice, rate, pitch, output_lrc, log, prog=lambda p, m: None) -> Path:
    import edge_tts  # type: ignore

    # 连通性预检
    log(f"☁ 测试网络连通性…")
    if not _test_edge_connectivity(log):
        log(f"[警告] 无法连接微软 TTS 服务, 尝试 SAPI5 / 占位音")
        if _has_sapi():
            sapi = _list_sapi_voices()
            pick = None
            for vid, desc, g in sapi:
                if "Chinese" in desc or "中文" in desc or "Huihui" in desc or "Yaoyao" in desc or "Tracy" in desc:
                    pick = vid
                    break
            if not pick and sapi:
                pick = sapi[0][0]
            if pick:
                return _tts_sapi(text, output, pick, rate, pitch, output_lrc, log, prog)
        return _tts_sine(text, output, rate, pitch, output_lrc, log, prog)

    async def _run():
        # rate: 0.5 - 2.0 -> -50% ~ +100%
        rate_pct = f"+{int((rate - 1) * 100)}%" if rate >= 1 else f"{int((rate - 1) * 100)}%"
        pitch_hz = f"+{int((pitch - 1) * 50)}Hz" if pitch >= 1 else f"{int((pitch - 1) * 50)}Hz"
        comm = edge_tts.Communicate(text, voice=voice, rate=rate_pct, pitch=pitch_hz)
        mp3 = output.with_suffix(".mp3")
        bytes_done = 0
        with open(mp3, "wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                    bytes_done += len(chunk["data"])
                    # 经验估算: 25 字符/秒, 每秒约 4KB MP3
                    est_total = max(8000, len(text) * 200)
                    p = min(0.7, 0.1 + (bytes_done / est_total) * 0.6)
                    prog(p, f"☁ 下载音频流 {bytes_done//1024}KB")
                elif chunk["type"] == "WordBoundary":
                    pass
        return mp3

    log(f"☁ edge-tts 合成中 ({voice}) …")
    prog(0.05, f"☁ 连接云端 ({voice})…")

    # 在 EXE 环境中, 主线程可能已有事件循环, 改用独立 loop
    mp3_path = None
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                raise RuntimeError("loop is running")
            mp3_path = loop.run_until_complete(_run())
        except RuntimeError:
            new_loop = asyncio.new_event_loop()
            try:
                mp3_path = new_loop.run_until_complete(_run())
            finally:
                new_loop.close()
    except Exception as e:
        log(f"[错误] edge-tts 失败: {type(e).__name__}: {e}")
        import traceback
        log(traceback.format_exc())
        log("[提示] 回退到占位音")
        return _tts_sine(text, output, rate, pitch, output_lrc, log, prog)

    # 转为 WAV
    try:
        from ..core import ffmpeg as _ff
        ffm = _ff.get_ffmpeg_path()
        prog(0.75, "🔄 MP3 转 WAV…")
        # 用 encoding='utf-8' + errors='replace' 避免 Windows GBK 解码错误
        creationflags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(
            [ffm, "-y", "-i", str(mp3_path), "-ar", "22050", "-ac", "1", str(output)],
            capture_output=True, text=False, timeout=60,
            creationflags=creationflags,
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")[-300:] if result.stderr else ""
            log(f"[警告] ffmpeg 转换失败 (rc={result.returncode}): {err}")
        mp3_path.unlink(missing_ok=True)
    except FileNotFoundError as e:
        log(f"[警告] ffmpeg 未找到: {e}, 改输出为 mp3")
        if mp3_path and mp3_path.exists():
            mp3_path.rename(output.with_suffix(".mp3"))
    except Exception as e:
        log(f"[警告] 转 WAV 失败: {e}, 改输出为 mp3")
        if mp3_path and mp3_path.exists():
            mp3_path.rename(output.with_suffix(".mp3"))

    if output.exists() and output_lrc:
        prog(0.9, "📝 写 LRC 歌词…")
        _write_lrc(text, output, output_lrc, log)
    log(f"✓ 已生成: {output.name}")
    return output


# ============================================================
# SAPI5 (Windows 本机)
# ============================================================
def _tts_sapi_first(text, output, rate, pitch, output_lrc, log, prog=lambda p, m: None) -> Path:
    sapi = _list_sapi_voices()
    # 优先选中文女声
    pick = None
    for vid, desc, g in sapi:
        if "Chinese" in desc or "中文" in desc or "Huihui" in desc or "Yaoyao" in desc or "Tracy" in desc:
            pick = vid
            break
    if not pick and sapi:
        pick = sapi[0][0]
    if not pick:
        return _tts_sine(text, output, rate, pitch, output_lrc, log, prog)
    return _tts_sapi(text, output, pick, rate, pitch, output_lrc, log, prog)


def _tts_sapi(text, output, voice_id, rate, pitch, output_lrc, log, prog=lambda p, m: None) -> Path:
    try:
        import win32com.client  # type: ignore
    except Exception:
        return _tts_sine(text, output, rate, pitch, output_lrc, log, prog)

    log(f"🖥 SAPI5 合成中 ({voice_id}) …")
    prog(0.1, f"🖥 SAPI5 合成…")
    sp = win32com.client.Dispatch("SAPI.SpVoice")
    cat = sp.GetVoices()
    for i in range(cat.Count):
        if cat.Item(i).GetAttribute("ID") == voice_id:
            sp.Voice = cat.Item(i)
            break
    sp.Rate = int((rate - 1) * 10)  # -10..+10
    # pitch 不直接支持, 跳过

    # 写到内存流
    import io
    fmt = win32com.client.Dispatch("SAPI.SpAudioFormat")
    fmt.Type = 22  # 16kHz 16-bit mono PCM
    stream = win32com.client.Dispatch("SAPI.SpFileStream")
    stream.Format = fmt
    stream.Open(str(output), 3, False)
    sp.AudioOutputStream = stream
    sp.Speak(text)
    stream.Close()

    if output.exists() and output_lrc:
        prog(0.9, "📝 写 LRC 歌词…")
        _write_lrc(text, output, output_lrc, log)
    log(f"✓ 已生成: {output.name}")
    return output


# ============================================================
# 占位: 正弦波
# ============================================================
def _tts_sine(text, output, rate, pitch, output_lrc, log, prog=lambda p, m: None) -> Path:
    log(f"🎵 占位音合成中 …")
    prog(0.2, "🎵 占位音合成中…")
    duration = max(1.0, len(text) / 4.0) / max(0.1, rate)
    sample_rate = 22050
    n_samples = int(sample_rate * duration)
    base_freq = 200 * max(0.5, min(2.0, pitch))

    with wave.open(str(output), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_samples):
            t = i / sample_rate
            sample = (
                0.5 * math.sin(2 * math.pi * base_freq * t)
                + 0.2 * math.sin(2 * math.pi * base_freq * 2 * t)
                + 0.1 * math.sin(2 * math.pi * base_freq * 3 * t)
            )
            env = 1.0
            if t < 0.05:
                env = t / 0.05
            elif t > duration - 0.05:
                env = (duration - t) / 0.05
            sample = sample * env * 0.4
            wf.writeframesraw(struct.pack("<h", int(sample * 32767)))
            if i % (sample_rate // 4) == 0:  # 每 0.25s 报一次
                p = 0.2 + 0.6 * (i / max(1, n_samples))
                prog(p, f"🎵 生成 {i//sample_rate}s / {int(duration)}s")

    if output_lrc:
        prog(0.9, "📝 写 LRC 歌词…")
        _write_lrc(text, output, output_lrc, log)
    log(f"✓ 已生成: {output.name}")
    return output


# ============================================================
# LRC 歌词文件 (按句生成时间戳)
# ============================================================
def _write_lrc(text: str, audio: Path, lrc: Path, log) -> Path:
    """根据字符数估算每句时长, 生成 [mm:ss.xx] 行"""
    # 用字符数 / 总字数 * 总时长 = 句子结束时间
    try:
        from ..core import ffmpeg as _ff
        ffm = _ff.get_ffmpeg_path()
        out = subprocess.run(
            [ffm, "-i", str(audio)],
            capture_output=True, text=True, timeout=10
        )
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", out.stderr)
        if m:
            total = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        else:
            total = max(1.0, len(text) / 4.0)
    except Exception:
        total = max(1.0, len(text) / 4.0)

    # 按标点切句
    sentences = re.split(r"([。!?！？\.\!\?\;；\n]+)", text)
    # 把标点合回前句
    lines = []
    for i in range(0, len(sentences) - 1, 2):
        s = (sentences[i] + sentences[i + 1]).strip()
        if s:
            lines.append(s)
    if not lines:
        lines = [text]

    total_chars = sum(len(ln) for ln in lines) or 1
    cur = 0.0
    lrc_lines = []
    for ln in lines:
        dur = total * (len(ln) / total_chars)
        mm = int(cur // 60)
        ss = cur - mm * 60
        lrc_lines.append(f"[{mm:02d}:{ss:05.2f}]{ln}")
        cur += dur

    lrc.parent.mkdir(parents=True, exist_ok=True)
    lrc.write_text("\n".join(lrc_lines) + "\n", encoding="utf-8")
    log(f"✓ LRC 歌词: {lrc.name}")
    return lrc
