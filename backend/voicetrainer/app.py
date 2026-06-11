import json
import os
from dataclasses import asdict

import numpy as np
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from voicetrainer.analysis.calibrate import analyze_vowel_recording
from voicetrainer.analysis.frame import analyze_frame
from voicetrainer.profiles import Profile, load_active, save
from voicetrainer.targets import builtin_default

app = FastAPI()

WINDOW_MS = 75  # 滚动分析窗;够 75Hz 下限取 ~5 个周期


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/target")
def target() -> dict:
    return asdict(load_active().target)


REQUIRED_VOWELS = {"a", "e", "i", "o", "u"}


@app.get("/api/profile")
def get_profile() -> dict:
    return load_active().to_dict()


class ProfileIn(BaseModel):
    vowel_templates: dict


@app.put("/api/profile")
def put_profile(payload: ProfileIn) -> dict:
    vt = payload.vowel_templates
    if set(vt.keys()) != REQUIRED_VOWELS:
        raise HTTPException(status_code=400, detail="需要全 5 个元音 a/e/i/o/u")
    templates = {k: [float(v[0]), float(v[1])] for k, v in vt.items()}
    profile = Profile(vowel_templates=templates, target=builtin_default(), source="calibrated")
    save(profile)
    return profile.to_dict()


@app.post("/api/calibrate")
async def calibrate(vowel: str, sampleRate: int, request: Request) -> dict:
    if vowel not in REQUIRED_VOWELS:
        raise HTTPException(status_code=400, detail="vowel 必须是 a/e/i/o/u 之一")
    raw = await request.body()
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    result = analyze_vowel_recording(samples, sampleRate)
    if result is None:
        return {"retake": True}
    f1, f2 = result
    return {"f1": f1, "f2": f2}


@app.websocket("/ws")
async def ws_realtime(websocket: WebSocket) -> None:
    await websocket.accept()
    profile = load_active()
    sample_rate = 48000
    buf = np.zeros(0, dtype=np.float32)
    try:
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                return
            text = msg.get("text")
            if text is not None:
                data = json.loads(text)
                if data.get("type") == "hello":
                    sample_rate = int(data.get("sampleRate", 48000))
                continue
            raw = msg.get("bytes")
            if raw is None:
                continue
            # 线格式约定:前端按 Int16 小端(LE)发送(见 frontend capture.ts);
            # 现代浏览器一律小端平台,故此处硬编码 "<i2"。
            chunk = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
            buf = np.concatenate([buf, chunk])
            win = int(sample_rate * WINDOW_MS / 1000)
            if buf.size > win:
                buf = buf[-win:]
            if buf.size < win:
                continue
            result = analyze_frame(buf, sample_rate, templates=profile.vowel_templates)
            payload = result.to_dict()
            payload.update(profile.target.contains(result.f0, result.resonance))
            await websocket.send_text(json.dumps(payload))
    except WebSocketDisconnect:
        return


# 静态托管放最后:开发时若没有 dist 目录则跳过(前端走 vite dev)。
_static_dir = os.environ.get(
    "STATIC_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"),
)
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
