"""M3U8 解析与下载合并"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import List, Tuple, Optional, Callable

import requests


def parse_m3u8(content: str, base_url: str) -> List[str]:
    """从 m3u8 文本解析片段 URL 列表"""
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    urls: List[str] = []
    for line in lines:
        if line.startswith("#"):
            continue
        if line.startswith("http://") or line.startswith("https://"):
            urls.append(line)
        else:
            # 相对路径
            if base_url.endswith("/"):
                urls.append(base_url + line)
            else:
                urls.append(base_url.rsplit("/", 1)[0] + "/" + line)
    return urls


def download_m3u8(
    source: str,
    on_log: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> Tuple[List[Path], Path]:
    """下载 m3u8 列表与所有片段, 返回 (片段路径列表, concat 列表文件路径)"""
    log = on_log or (lambda m: None)

    if source.startswith("http://") or source.startswith("https://"):
        log(f"下载 m3u8: {source}")
        r = requests.get(source, timeout=30)
        r.raise_for_status()
        content = r.text
        base = source.rsplit("/", 1)[0]
    else:
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"找不到 m3u8 文件: {source}")
        content = path.read_text(encoding="utf-8")
        base = str(path.parent)

    urls = parse_m3u8(content, base)
    if not urls:
        raise RuntimeError("m3u8 中没有找到视频片段")

    log(f"共 {len(urls)} 个片段")

    out_dir = Path.home() / ".liuguangliyun" / "m3u8_cache" / str(int(time.time()))
    out_dir.mkdir(parents=True, exist_ok=True)

    files: List[Path] = []
    headers = {"User-Agent": "Mozilla/5.0", "Referer": base}
    for i, u in enumerate(urls):
        if on_progress:
            on_progress(i, len(urls))
        try:
            log(f"[{i+1}/{len(urls)}] {u}")
            rr = requests.get(u, timeout=60, headers=headers)
            rr.raise_for_status()
            ext = u.split("?")[0].split(".")[-1] or "ts"
            f = out_dir / f"seg_{i:05d}.{ext}"
            f.write_bytes(rr.content)
            files.append(f)
        except Exception as e:
            log(f"[失败] {u}: {e}")

    if not files:
        raise RuntimeError("所有片段下载失败")

    # 写 concat 列表
    list_file = out_dir / "_concat.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for fp in files:
            p = str(fp.resolve()).replace("\\", "/")
            f.write(f"file '{p}'\n")

    if on_progress:
        on_progress(len(urls), len(urls))
    log(f"已下载 {len(files)} 个片段, 列表: {list_file}")
    return files, list_file
