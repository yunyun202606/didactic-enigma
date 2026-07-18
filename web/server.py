"""流光璃韵 · Web 版后端服务"""
from __future__ import annotations

import os
import sys
import time
import uuid
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.tools import ALL_TOOLS, TOOL_MAP

UPLOAD_DIR = ROOT / "web" / "uploads"
OUTPUT_DIR = ROOT / "web" / "outputs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_jobs: Dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    for job in _jobs.values():
        if "proc" in job and job["proc"]:
            try:
                job["proc"].terminate()
            except Exception:
                pass


app = FastAPI(title="流光璃韵 Web", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _tool_to_dict(tool) -> dict:
    return {
        "id": tool.id,
        "name": tool.name,
        "desc": tool.desc,
        "category": tool.category,
        "icon": tool.icon,
        "color": tool.color,
        "input_kind": tool.input_kind,
        "output_ext": tool.output_ext,
        "params": [
            {
                "key": p.key,
                "label": p.label,
                "kind": p.kind,
                "default": p.default,
                "suffix": p.suffix,
                "min": p.min,
                "max": p.max,
                "step": p.step,
                "options": [{"value": v, "label": l} for v, l in p.options],
                "placeholder": p.placeholder,
            }
            for p in tool.params
        ],
    }


@app.get("/api/tools")
async def list_tools():
    return {
        "tools": [_tool_to_dict(t) for t in ALL_TOOLS],
        "categories": sorted(set(t.category for t in ALL_TOOLS)),
    }


@app.get("/api/tools/{tool_id}")
async def get_tool(tool_id: str):
    if tool_id not in TOOL_MAP:
        raise HTTPException(status_code=404, detail="工具不存在")
    return _tool_to_dict(TOOL_MAP[tool_id])


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix if file.filename else ""
    save_name = f"{uuid.uuid4().hex}{ext}"
    save_path = UPLOAD_DIR / save_name
    content = await file.read()
    save_path.write_bytes(content)
    return {
        "id": save_name,
        "name": file.filename,
        "size": len(content),
        "url": f"/uploads/{save_name}",
    }


@app.post("/api/ocr/id-card")
async def ocr_id_card(
    file: UploadFile = File(...),
    doc_type: str = Form("auto"),
    engine: str = Form("auto"),
    save_raw: bool = Form(False),
):
    ext = Path(file.filename).suffix if file.filename else ".png"
    img_name = f"{uuid.uuid4().hex}{ext}"
    img_path = UPLOAD_DIR / img_name
    content = await file.read()
    img_path.write_bytes(content)

    try:
        from app.core.id_card_ocr import extract_id_info, save_result

        info = extract_id_info(str(img_path), doc_type=doc_type, engine=engine)
        if not save_raw and "raw_text" in info:
            del info["raw_text"]

        ts = int(time.time())
        out_name = f"id_ocr_{ts}.json"
        out_path = OUTPUT_DIR / out_name
        save_result(info, out_path)

        return {
            "success": True,
            "result": info,
            "output": f"/outputs/{out_name}",
        }
    except ImportError as e:
        raise HTTPException(status_code=400, detail=f"OCR 依赖未安装: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"识别失败: {e}")


@app.get("/api/tts/voices")
async def tts_voices():
    try:
        from app.core.tts import list_voices
        return {"voices": list_voices()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tts/synth")
async def tts_synth(
    text: str = Form(...),
    voice: str = Form("edge:zh-CN-XiaoxiaoNeural"),
    rate: float = Form(1.0),
    pitch: float = Form(1.0),
    output_lrc: bool = Form(True),
):
    job_id = uuid.uuid4().hex
    ts = int(time.time())
    out_wav = OUTPUT_DIR / f"tts_{ts}_{job_id}.wav"
    out_lrc = OUTPUT_DIR / f"tts_{ts}_{job_id}.lrc" if output_lrc else None

    _jobs[job_id] = {
        "id": job_id,
        "type": "tts",
        "status": "running",
        "progress": 0,
        "logs": [],
        "result": None,
    }

    import threading

    def _run():
        try:
            from app.core.tts import tts_to_wav

            def on_log(msg):
                _jobs[job_id]["logs"].append(msg)
                if len(_jobs[job_id]["logs"]) > 100:
                    _jobs[job_id]["logs"] = _jobs[job_id]["logs"][-100:]

            def on_progress(p, msg):
                _jobs[job_id]["progress"] = int(p * 100)
                _jobs[job_id]["status_msg"] = msg

            tts_to_wav(
                text=text,
                output=out_wav,
                voice_id=voice,
                rate=rate,
                pitch=pitch,
                output_lrc=out_lrc,
                on_log=on_log,
                on_progress=on_progress,
            )

            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["progress"] = 100
            _jobs[job_id]["result"] = {
                "audio": f"/outputs/{out_wav.name}",
                "lrc": f"/outputs/{out_lrc.name}" if out_lrc and out_lrc.exists() else None,
            }
        except Exception as e:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(e)

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _jobs[job_id]


app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

WEB_DIR = ROOT / "web" / "static"
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
