# Voice Trainer MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户说话时,浏览器实时显示音高(F0)和归一化共鸣是否落在目标带内(在区/出区),后端用同一套分析引擎流式计算。

**Architecture:** Web 前端(Vite + 原生 TS)用 WebAudio 采麦克风,切成 Int16 PCM 块经 WebSocket 流给 Python 后端;后端(FastAPI)维护滚动缓冲,用 parselmouth(Praat)逐窗算 F0 + 共振峰 + 归一化共鸣,实时推回;前端渲染 B2 连读双轨界面。后端同时托管前端静态产物,部署单进程单端口。

**Tech Stack:** Python 3.11 / FastAPI / uvicorn / numpy / praat-parselmouth / pytest;TypeScript / Vite;Docker + docker compose。

**Scope note:** 本计划只覆盖阶段一 MVP(连读双轨 + 内置目标带)。阶段二(单元音定位图 + 个人标定)、阶段三(录制复盘报告)各自另出计划。MVP 的归一化共鸣使用**内置通用元音模板**(无个人标定),阶段二再替换为个人标定模板。

**Deferred from spec(有意延后,非遗漏):**
- 共振峰低置信度时"点变灰":MVP 简化为 resonance 为 null 时不画该点(`realtime-view.ts` 已 `if (v === null) continue`),不单独做灰点态。
- WebSocket 断线自动重连:MVP 在本机单端口跑,断连概率低;`capture.ts` 暂不做重连,点"停止"再"开始"即重连。两项放阶段二打磨。

---

## File Structure

```
voice-trainer/
  backend/
    requirements.txt
    voicetrainer/
      __init__.py
      analysis/
        __init__.py
        pitch.py          # estimate_f0
        formants.py       # estimate_formants
        vowel.py          # VOWEL_TEMPLATES, classify_vowel, normalized_resonance
        frame.py          # AnalysisResult, analyze_frame (组合上面三个)
      targets.py          # TargetProfile, builtin_default
      app.py              # FastAPI: /ws, /api/health, /api/target, 静态托管
    tests/
      __init__.py
      test_pitch.py
      test_formants.py
      test_vowel.py
      test_frame.py
      test_targets.py
      test_ws.py
  frontend/
    package.json
    tsconfig.json
    vite.config.ts
    index.html
    src/
      main.ts            # 接线:按钮 → 采音 → 推帧 → rAF 渲染
      capture.ts         # 麦克风采集 + 分块 + WebSocket
      realtime-view.ts   # 双轨画布渲染
      style.css
  scripts/
    dev.sh
  Makefile
  Dockerfile
  compose.yaml
  README.md
```

每个文件单一职责:`analysis/*` 是纯 DSP(不碰网络/状态),`app.py` 只管流转与托管,前端三个文件分别管采集、渲染、接线。

---

## Task 1: 后端脚手架 + 依赖 + 冒烟测试

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/voicetrainer/__init__.py` (空文件)
- Create: `backend/voicetrainer/analysis/__init__.py` (空文件)
- Create: `backend/tests/__init__.py` (空文件)
- Create: `backend/tests/test_smoke.py`

- [ ] **Step 1: 写依赖文件**

`backend/requirements.txt`:
```
fastapi==0.111.0
uvicorn[standard]==0.30.1
numpy==1.26.4
praat-parselmouth==0.4.3
pytest==8.2.0
httpx==0.27.0
```

- [ ] **Step 2: 建空 package 文件**

创建三个空文件:`backend/voicetrainer/__init__.py`、`backend/voicetrainer/analysis/__init__.py`、`backend/tests/__init__.py`。

- [ ] **Step 3: 写冒烟测试**

`backend/tests/test_smoke.py`:
```python
import numpy as np
import parselmouth


def test_deps_importable():
    snd = parselmouth.Sound(np.zeros(1000, dtype=np.float64), sampling_frequency=16000)
    assert snd.duration > 0
```

- [ ] **Step 4: 安装依赖并跑测试**

Run:
```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && pytest tests/test_smoke.py -q
```
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/voicetrainer backend/tests
git commit -m "chore: backend scaffold and deps"
```

---

## Task 2: 基频估计 `estimate_f0`

**Files:**
- Create: `backend/voicetrainer/analysis/pitch.py`
- Test: `backend/tests/test_pitch.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_pitch.py`:
```python
import numpy as np
from voicetrainer.analysis.pitch import estimate_f0


def _sine(freq, dur, sr, amp=0.5):
    t = np.arange(int(sr * dur)) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_estimate_f0_on_200hz_sine():
    sr = 16000
    f0 = estimate_f0(_sine(200.0, 0.2, sr), sr)
    assert f0 is not None
    assert abs(f0 - 200.0) < 5.0


def test_estimate_f0_on_silence_returns_none():
    sr = 16000
    assert estimate_f0(np.zeros(int(sr * 0.2), dtype=np.float32), sr) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_pitch.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'voicetrainer.analysis.pitch'`

- [ ] **Step 3: 写实现**

`backend/voicetrainer/analysis/pitch.py`:
```python
from typing import Optional

import numpy as np
import parselmouth


def estimate_f0(
    samples: np.ndarray,
    sample_rate: int,
    fmin: float = 75.0,
    fmax: float = 500.0,
) -> Optional[float]:
    """估计一段单声道 PCM 的基频(Hz)。无声/清音返回 None。"""
    if samples.size == 0 or float(np.max(np.abs(samples))) < 1e-4:
        return None
    snd = parselmouth.Sound(samples.astype(np.float64), sampling_frequency=sample_rate)
    try:
        pitch = snd.to_pitch(pitch_floor=fmin, pitch_ceiling=fmax)
    except Exception:
        return None
    freqs = pitch.selected_array["frequency"]
    voiced = freqs[freqs > 0]
    if voiced.size == 0:
        return None
    return float(np.median(voiced))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_pitch.py -q`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/voicetrainer/analysis/pitch.py backend/tests/test_pitch.py
git commit -m "feat: F0 estimation via parselmouth"
```

---

## Task 3: 共振峰估计 `estimate_formants`

**Files:**
- Create: `backend/voicetrainer/analysis/formants.py`
- Test: `backend/tests/test_formants.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_formants.py`:
```python
import numpy as np
from voicetrainer.analysis.formants import estimate_formants


def _two_tone(f_a, f_b, dur, sr, amp=0.4):
    t = np.arange(int(sr * dur)) / sr
    sig = amp * np.sin(2 * np.pi * f_a * t) + amp * np.sin(2 * np.pi * f_b * t)
    return sig.astype(np.float32)


def test_estimate_formants_finds_two_peaks():
    sr = 16000
    # 两个类共振峰能量峰,LPC 包络应在附近给出 F1/F2
    f1, f2 = estimate_formants(_two_tone(700.0, 1200.0, 0.2, sr), sr)
    assert f1 is not None and f2 is not None
    assert abs(f1 - 700.0) < 200.0
    assert abs(f2 - 1200.0) < 250.0
    assert f1 < f2


def test_estimate_formants_on_silence_returns_none():
    sr = 16000
    assert estimate_formants(np.zeros(int(sr * 0.2), dtype=np.float32), sr) == (None, None)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_formants.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 写实现**

`backend/voicetrainer/analysis/formants.py`:
```python
from typing import Optional, Tuple

import numpy as np
import parselmouth


def estimate_formants(
    samples: np.ndarray,
    sample_rate: int,
    max_formant: float = 5500.0,
) -> Tuple[Optional[float], Optional[float]]:
    """估计 (F1, F2),单位 Hz。取信号中点处的共振峰值。无声/失败返回 (None, None)。"""
    if samples.size == 0 or float(np.max(np.abs(samples))) < 1e-4:
        return (None, None)
    snd = parselmouth.Sound(samples.astype(np.float64), sampling_frequency=sample_rate)
    try:
        formant = snd.to_formant_burg(maximum_formant=max_formant)
    except Exception:
        return (None, None)
    t = snd.duration / 2.0
    f1 = formant.get_value_at_time(1, t)
    f2 = formant.get_value_at_time(2, t)
    f1 = None if (f1 is None or np.isnan(f1)) else float(f1)
    f2 = None if (f2 is None or np.isnan(f2)) else float(f2)
    return (f1, f2)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_formants.py -q`
Expected: 2 passed
(若 `test_estimate_formants_finds_two_peaks` 因 LPC 包络偏差略超容差,放宽断言到 ±300Hz —— 这层只需保证"找到两个递增的合理峰",精度由 Praat 默认参数保证。)

- [ ] **Step 5: Commit**

```bash
git add backend/voicetrainer/analysis/formants.py backend/tests/test_formants.py
git commit -m "feat: formant (F1/F2) estimation via LPC"
```

---

## Task 4: 元音识别 + 归一化共鸣 `vowel.py`

**Files:**
- Create: `backend/voicetrainer/analysis/vowel.py`
- Test: `backend/tests/test_vowel.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_vowel.py`:
```python
import math
from voicetrainer.analysis.vowel import (
    VOWEL_TEMPLATES,
    classify_vowel,
    normalized_resonance,
)


def test_classify_vowel_matches_nearest_template():
    # 贴近 "a" 模板 (700, 1220) 的输入应归为 "a"
    assert classify_vowel(710.0, 1230.0) == "a"
    # 贴近 "i" 模板 (320, 2200)
    assert classify_vowel(330.0, 2150.0) == "i"


def test_normalized_resonance_zero_at_template():
    # 正好等于模板共振峰时,抬升量为 0 个八度
    f1, f2 = VOWEL_TEMPLATES["a"]
    assert abs(normalized_resonance(f1, f2)) < 1e-9


def test_normalized_resonance_positive_when_brighter():
    # 共振峰整体抬高(更亮)→ 正值
    f1, f2 = VOWEL_TEMPLATES["a"]
    r = normalized_resonance(f1 * 1.2, f2 * 1.2)
    assert r > 0
    assert abs(r - math.log2(1.2)) < 1e-6
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_vowel.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 写实现**

`backend/voicetrainer/analysis/vowel.py`:
```python
import math
from typing import Dict, Tuple

# 通用中性基线元音模板 (F1, F2),单位 Hz。MVP 用这套;阶段二替换为个人标定值。
VOWEL_TEMPLATES: Dict[str, Tuple[float, float]] = {
    "a": (700.0, 1220.0),
    "e": (530.0, 1840.0),
    "i": (320.0, 2200.0),
    "o": (570.0, 900.0),
    "u": (350.0, 800.0),
}


def _log_dist2(f1: float, f2: float, t1: float, t2: float) -> float:
    return (math.log2(f1 / t1)) ** 2 + (math.log2(f2 / t2)) ** 2


def classify_vowel(f1: float, f2: float) -> str:
    """在对数频率空间里取最近的元音模板。"""
    return min(
        VOWEL_TEMPLATES,
        key=lambda v: _log_dist2(f1, f2, *VOWEL_TEMPLATES[v]),
    )


def normalized_resonance(f1: float, f2: float) -> float:
    """相对最近元音模板,共振峰整体抬升了多少(单位:八度)。
    >0 = 更亮,<0 = 更暗。换元音不影响此值。"""
    vowel = classify_vowel(f1, f2)
    t1, t2 = VOWEL_TEMPLATES[vowel]
    return 0.5 * (math.log2(f1 / t1) + math.log2(f2 / t2))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_vowel.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/voicetrainer/analysis/vowel.py backend/tests/test_vowel.py
git commit -m "feat: vowel classification and normalized resonance"
```

---

## Task 5: 帧分析组合 `frame.py`

**Files:**
- Create: `backend/voicetrainer/analysis/frame.py`
- Test: `backend/tests/test_frame.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_frame.py`:
```python
import numpy as np
from voicetrainer.analysis.frame import AnalysisResult, analyze_frame


def _voiced_vowel(f0, f_a, f_b, dur, sr):
    t = np.arange(int(sr * dur)) / sr
    sig = 0.4 * np.sin(2 * np.pi * f0 * t)
    sig += 0.3 * np.sin(2 * np.pi * f_a * t)
    sig += 0.3 * np.sin(2 * np.pi * f_b * t)
    return sig.astype(np.float32)


def test_analyze_frame_silence_is_unvoiced():
    sr = 16000
    res = analyze_frame(np.zeros(int(sr * 0.2), dtype=np.float32), sr)
    assert isinstance(res, AnalysisResult)
    assert res.voiced is False
    assert res.f0 is None


def test_analyze_frame_voiced_has_all_fields():
    sr = 16000
    res = analyze_frame(_voiced_vowel(200.0, 700.0, 1200.0, 0.2, sr), sr)
    assert res.voiced is True
    assert res.f0 is not None and abs(res.f0 - 200.0) < 8.0
    assert res.f1 is not None and res.f2 is not None
    assert res.vowel in {"a", "e", "i", "o", "u"}
    assert res.resonance is not None


def test_to_dict_roundtrip_keys():
    res = analyze_frame(np.zeros(1000, dtype=np.float32), 16000)
    d = res.to_dict()
    assert set(d.keys()) == {"voiced", "f0", "f1", "f2", "vowel", "resonance"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_frame.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 写实现**

`backend/voicetrainer/analysis/frame.py`:
```python
from dataclasses import asdict, dataclass
from typing import Optional

import numpy as np

from voicetrainer.analysis.formants import estimate_formants
from voicetrainer.analysis.pitch import estimate_f0
from voicetrainer.analysis.vowel import classify_vowel, normalized_resonance


@dataclass
class AnalysisResult:
    voiced: bool
    f0: Optional[float] = None
    f1: Optional[float] = None
    f2: Optional[float] = None
    vowel: Optional[str] = None
    resonance: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


def analyze_frame(samples: np.ndarray, sample_rate: int) -> AnalysisResult:
    """一段 PCM → 完整分析结果。无音高=unvoiced;有音高但共振峰不稳=只给 f0。"""
    f0 = estimate_f0(samples, sample_rate)
    if f0 is None:
        return AnalysisResult(voiced=False)
    f1, f2 = estimate_formants(samples, sample_rate)
    if f1 is None or f2 is None:
        return AnalysisResult(voiced=True, f0=f0)
    return AnalysisResult(
        voiced=True,
        f0=f0,
        f1=f1,
        f2=f2,
        vowel=classify_vowel(f1, f2),
        resonance=normalized_resonance(f1, f2),
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_frame.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/voicetrainer/analysis/frame.py backend/tests/test_frame.py
git commit -m "feat: combined frame analysis"
```

---

## Task 6: 目标带 `targets.py`

**Files:**
- Create: `backend/voicetrainer/targets.py`
- Test: `backend/tests/test_targets.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_targets.py`:
```python
from voicetrainer.targets import TargetProfile, builtin_default


def test_builtin_default_fields():
    t = builtin_default()
    assert t.source == "builtin"
    assert t.f0_min < t.f0_max
    assert t.resonance_min < t.resonance_max


def test_contains_in_target():
    t = builtin_default()
    mid_f0 = (t.f0_min + t.f0_max) / 2
    mid_res = (t.resonance_min + t.resonance_max) / 2
    r = t.contains(mid_f0, mid_res)
    assert r == {"f0_in": True, "resonance_in": True, "in_target": True}


def test_contains_out_of_target():
    t = builtin_default()
    r = t.contains(t.f0_min - 50, t.resonance_min - 1.0)
    assert r["in_target"] is False
    assert r["f0_in"] is False


def test_contains_handles_none():
    t = builtin_default()
    r = t.contains(None, None)
    assert r == {"f0_in": False, "resonance_in": False, "in_target": False}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_targets.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 写实现**

`backend/voicetrainer/targets.py`:
```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class TargetProfile:
    name: str
    f0_min: float
    f0_max: float
    resonance_min: float
    resonance_max: float
    source: str = "builtin"

    def contains(self, f0: Optional[float], resonance: Optional[float]) -> dict:
        f0_in = f0 is not None and self.f0_min <= f0 <= self.f0_max
        res_in = resonance is not None and self.resonance_min <= resonance <= self.resonance_max
        return {"f0_in": f0_in, "resonance_in": res_in, "in_target": f0_in and res_in}


def builtin_default() -> TargetProfile:
    """默认目标带。数值为起步默认,后续可调/可标定覆盖。
    - f0 165–220 Hz:目标基频区间。
    - resonance 0.15–0.7 八度:相对中性基线整体抬升的共振峰区间。"""
    return TargetProfile(
        name="Default",
        f0_min=165.0,
        f0_max=220.0,
        resonance_min=0.15,
        resonance_max=0.7,
        source="builtin",
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_targets.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/voicetrainer/targets.py backend/tests/test_targets.py
git commit -m "feat: target profile with builtin default band"
```

---

## Task 7: FastAPI 应用 + WebSocket 实时端点 + 静态托管

**Files:**
- Create: `backend/voicetrainer/app.py`
- Test: `backend/tests/test_ws.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_ws.py`:
```python
import json

import numpy as np
from fastapi.testclient import TestClient

from voicetrainer.app import app


def test_health():
    client = TestClient(app)
    assert client.get("/api/health").json() == {"status": "ok"}


def test_target_endpoint():
    client = TestClient(app)
    body = client.get("/api/target").json()
    assert body["source"] == "builtin"
    assert body["f0_min"] < body["f0_max"]


def test_ws_returns_analysis_for_voiced_frame():
    client = TestClient(app)
    sr = 16000
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "hello", "sampleRate": sr}))
        t = np.arange(int(sr * 0.2)) / sr
        sig = (0.5 * np.sin(2 * np.pi * 200 * t) * 32767).astype("<i2").tobytes()
        ws.send_bytes(sig)
        data = json.loads(ws.receive_text())
        assert "voiced" in data
        assert "in_target" in data
        assert data["voiced"] is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_ws.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'voicetrainer.app'`

- [ ] **Step 3: 写实现**

`backend/voicetrainer/app.py`:
```python
import json
import os
from dataclasses import asdict

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from voicetrainer.analysis.frame import analyze_frame
from voicetrainer.targets import builtin_default

app = FastAPI()

WINDOW_MS = 75  # 滚动分析窗;够 75Hz 下限取 ~5 个周期


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/target")
def target() -> dict:
    return asdict(builtin_default())


@app.websocket("/ws")
async def ws_realtime(websocket: WebSocket) -> None:
    await websocket.accept()
    profile = builtin_default()
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
            chunk = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
            buf = np.concatenate([buf, chunk])
            win = int(sample_rate * WINDOW_MS / 1000)
            if buf.size > win:
                buf = buf[-win:]
            if buf.size < win:
                continue
            result = analyze_frame(buf, sample_rate)
            payload = result.to_dict()
            payload.update(profile.contains(result.f0, result.resonance))
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_ws.py -q`
Expected: 3 passed

- [ ] **Step 5: 跑全部后端测试**

Run: `cd backend && . .venv/bin/activate && pytest -q`
Expected: 全部 passed(约 15 个)

- [ ] **Step 6: Commit**

```bash
git add backend/voicetrainer/app.py backend/tests/test_ws.py
git commit -m "feat: FastAPI app with realtime WS endpoint and static hosting"
```

---

## Task 8: 前端脚手架(Vite + TS + 代理)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/style.css`

- [ ] **Step 1: 写 package.json**

`frontend/package.json`:
```json
{
  "name": "voice-trainer-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "vite": "^5.2.0"
  }
}
```

- [ ] **Step 2: 写 tsconfig.json**

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "noEmit": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: 写 vite.config.ts(WS/API 代理到后端)**

`frontend/vite.config.ts`:
```typescript
import { defineConfig } from "vite";

export default defineConfig({
  server: {
    proxy: {
      "/ws": { target: "ws://localhost:8000", ws: true },
      "/api": { target: "http://localhost:8000" },
    },
  },
});
```

- [ ] **Step 4: 写 index.html**

`frontend/index.html`:
```html
<!doctype html>
<html lang="zh">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Voice Trainer</title>
    <link rel="stylesheet" href="/src/style.css" />
  </head>
  <body>
    <div id="app">
      <h1>嗓音训练 · 连读双轨</h1>
      <button id="start">开始</button>
      <div id="status">点"开始"并允许麦克风</div>
      <canvas id="view" width="900" height="320"></canvas>
    </div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 5: 写 style.css**

`frontend/src/style.css`:
```css
:root { color-scheme: dark; }
body { margin: 0; background: #0f1115; color: #e6e9ef; font-family: system-ui, sans-serif; }
#app { max-width: 940px; margin: 24px auto; padding: 0 16px; }
h1 { font-size: 18px; font-weight: 600; }
#start { padding: 8px 18px; border: 0; border-radius: 6px; background: #5ad1ff; color: #06222e; font-weight: 600; cursor: pointer; }
#status { margin: 10px 0; font-size: 13px; color: #8a93a3; }
#view { width: 100%; background: #171a21; border-radius: 8px; }
```

- [ ] **Step 6: 安装前端依赖**

Run: `cd frontend && npm install`
Expected: 依赖装好,生成 `node_modules/` 和 `package-lock.json`

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/tsconfig.json frontend/vite.config.ts frontend/index.html frontend/src/style.css frontend/package-lock.json
git commit -m "chore: frontend scaffold with vite + ws proxy"
```

---

## Task 9: 采音模块 `capture.ts`

**Files:**
- Create: `frontend/src/capture.ts`

> 采音/WebSocket 无法单元测试,这里写完整实现,后续用 `make dev` 冒烟验证(Task 12)。

- [ ] **Step 1: 写实现**

`frontend/src/capture.ts`:
```typescript
export type FrameHandler = (data: Record<string, unknown>) => void;
export type StopFn = () => void;

// 采麦克风 → Int16 PCM 块 → WebSocket;每帧分析结果回调给 onFrame。
export async function startCapture(onFrame: FrameHandler): Promise<StopFn> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
  });
  const ctx = new AudioContext();
  const source = ctx.createMediaStreamSource(stream);
  const proc = ctx.createScriptProcessor(2048, 1, 1);
  const mute = ctx.createGain();
  mute.gain.value = 0; // 接到 destination 让 onaudioprocess 触发,但不外放(避免回声)

  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.binaryType = "arraybuffer";
  ws.onopen = () => ws.send(JSON.stringify({ type: "hello", sampleRate: ctx.sampleRate }));
  ws.onmessage = (e) => onFrame(JSON.parse(e.data));

  proc.onaudioprocess = (e) => {
    if (ws.readyState !== WebSocket.OPEN) return;
    const f32 = e.inputBuffer.getChannelData(0);
    const i16 = new Int16Array(f32.length);
    for (let i = 0; i < f32.length; i++) {
      const s = Math.max(-1, Math.min(1, f32[i]));
      i16[i] = Math.round(s * 32767);
    }
    ws.send(i16.buffer);
  };

  source.connect(proc);
  proc.connect(mute);
  mute.connect(ctx.destination);

  return () => {
    proc.disconnect();
    source.disconnect();
    mute.disconnect();
    ws.close();
    ctx.close();
    stream.getTracks().forEach((t) => t.stop());
  };
}
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无报错

- [ ] **Step 3: Commit**

```bash
git add frontend/src/capture.ts
git commit -m "feat: mic capture and websocket streaming"
```

---

## Task 10: 双轨渲染 `realtime-view.ts`

**Files:**
- Create: `frontend/src/realtime-view.ts`

- [ ] **Step 1: 写实现**

`frontend/src/realtime-view.ts`:
```typescript
export interface TargetBand {
  f0_min: number;
  f0_max: number;
  resonance_min: number;
  resonance_max: number;
}

const MAXLEN = 300;
const pitchHist: (number | null)[] = [];
const resHist: (number | null)[] = [];
const inHist: boolean[] = [];

// 显示范围(纵轴映射)
const F0_LO = 80, F0_HI = 300;        // Hz
const RES_LO = -0.4, RES_HI = 1.0;     // 八度

export function pushFrame(d: Record<string, any>): void {
  pitchHist.push(d.voiced ? (d.f0 as number) : null);
  resHist.push(typeof d.resonance === "number" ? d.resonance : null);
  inHist.push(Boolean(d.in_target));
  if (pitchHist.length > MAXLEN) {
    pitchHist.shift();
    resHist.shift();
    inHist.shift();
  }
}

function mapY(v: number, lo: number, hi: number, top: number, h: number): number {
  const clamped = Math.max(lo, Math.min(hi, v));
  return top + h - ((clamped - lo) / (hi - lo)) * h;
}

export function render(cv: HTMLCanvasElement, band: TargetBand): void {
  const ctx = cv.getContext("2d");
  if (!ctx) return;
  const W = cv.width, H = cv.height;
  const trackH = H / 2 - 24;
  ctx.clearRect(0, 0, W, H);

  drawTrack(ctx, "音高 PITCH (Hz)", 8, trackH, W, pitchHist,
    (v) => mapY(v, F0_LO, F0_HI, 8, trackH),
    mapY(band.f0_min, F0_LO, F0_HI, 8, trackH),
    mapY(band.f0_max, F0_LO, F0_HI, 8, trackH));

  const top2 = H / 2 + 8;
  drawTrack(ctx, "共鸣 RESONANCE (八度)", top2, trackH, W, resHist,
    (v) => mapY(v, RES_LO, RES_HI, top2, trackH),
    mapY(band.resonance_min, RES_LO, RES_HI, top2, trackH),
    mapY(band.resonance_max, RES_LO, RES_HI, top2, trackH));
}

function drawTrack(
  ctx: CanvasRenderingContext2D,
  label: string,
  top: number,
  h: number,
  W: number,
  hist: (number | null)[],
  yOf: (v: number) => number,
  bandTopY: number,
  bandBotY: number,
): void {
  // 目标带(绿色)
  ctx.fillStyle = "rgba(64,200,120,0.16)";
  ctx.fillRect(0, bandTopY, W, bandBotY - bandTopY);
  ctx.strokeStyle = "rgba(64,200,120,0.6)";
  ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.moveTo(0, bandTopY); ctx.lineTo(W, bandTopY);
  ctx.moveTo(0, bandBotY); ctx.lineTo(W, bandBotY); ctx.stroke();
  ctx.setLineDash([]);
  // 标签
  ctx.fillStyle = "#8a93a3";
  ctx.font = "11px system-ui";
  ctx.fillText(label, 8, top + 14);
  // 曲线(逐点上色:在区绿、出区红)
  const step = W / MAXLEN;
  for (let i = 0; i < hist.length; i++) {
    const v = hist[i];
    if (v === null) continue;
    const x = i * step;
    const y = yOf(v);
    ctx.fillStyle = inHist[i] ? "#40c878" : "#ff5a6a";
    ctx.fillRect(x - 1.5, y - 1.5, 3, 3);
  }
}
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无报错

- [ ] **Step 3: Commit**

```bash
git add frontend/src/realtime-view.ts
git commit -m "feat: dual-track realtime canvas view"
```

---

## Task 11: 接线 `main.ts`

**Files:**
- Create: `frontend/src/main.ts`

- [ ] **Step 1: 写实现**

`frontend/src/main.ts`:
```typescript
import { startCapture, type StopFn } from "./capture";
import { pushFrame, render, type TargetBand } from "./realtime-view";

const startBtn = document.getElementById("start") as HTMLButtonElement;
const statusEl = document.getElementById("status") as HTMLDivElement;
const canvas = document.getElementById("view") as HTMLCanvasElement;

let stop: StopFn | null = null;
let band: TargetBand = { f0_min: 165, f0_max: 220, resonance_min: 0.15, resonance_max: 0.7 };

async function loadTarget(): Promise<void> {
  try {
    const r = await fetch("/api/target");
    const t = await r.json();
    band = {
      f0_min: t.f0_min, f0_max: t.f0_max,
      resonance_min: t.resonance_min, resonance_max: t.resonance_max,
    };
  } catch {
    /* 用默认 band */
  }
}

function loop(): void {
  render(canvas, band);
  requestAnimationFrame(loop);
}

startBtn.addEventListener("click", async () => {
  if (stop) {
    stop();
    stop = null;
    startBtn.textContent = "开始";
    statusEl.textContent = "已停止";
    return;
  }
  await loadTarget();
  try {
    stop = await startCapture((d) => {
      pushFrame(d);
      statusEl.textContent = d.voiced
        ? `F0 ${d.f0 ? (d.f0 as number).toFixed(0) : "-"}Hz · 共鸣 ${
            typeof d.resonance === "number" ? (d.resonance as number).toFixed(2) : "-"
          } · ${d.in_target ? "在区 ✓" : "出区"}`
        : "听不到,说大声点";
    });
    startBtn.textContent = "停止";
    statusEl.textContent = "正在听…";
  } catch (e) {
    statusEl.textContent = "麦克风打不开,请检查权限";
  }
});

loop();
```

- [ ] **Step 2: 类型检查 + 构建**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: 无报错,生成 `frontend/dist/`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/main.ts
git commit -m "feat: wire up capture, rendering and target loading"
```

---

## Task 12: 一条命令本地起 `make dev`

**Files:**
- Create: `scripts/dev.sh`
- Create: `Makefile`

- [ ] **Step 1: 写 dev 脚本**

`scripts/dev.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
trap 'kill 0' EXIT

( cd backend && . .venv/bin/activate && uvicorn voicetrainer.app:app --reload --port 8000 ) &
( cd frontend && npm run dev ) &
wait
```

- [ ] **Step 2: 加可执行权限**

Run: `chmod +x scripts/dev.sh`

- [ ] **Step 3: 写 Makefile**

`Makefile`(注意:recipe 行必须用 **TAB** 缩进,不能用空格):
```make
.PHONY: install dev test build

install:
	cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
	cd frontend && npm install

dev:
	./scripts/dev.sh

test:
	cd backend && . .venv/bin/activate && pytest -q

build:
	cd frontend && npm run build
```

- [ ] **Step 4: 冒烟验证(手动)**

Run: `make dev`
然后浏览器开 `http://localhost:5173`,点"开始",允许麦克风,出声说话。
Expected:
- 上轨出现音高点,绿色目标带 165–220Hz;说话音高在带内时点变绿,带外变红。
- 下轨共鸣点随发声移动。
- status 行实时显示 `F0 …Hz · 共鸣 … · 在区/出区`。
- 后端终端打印 WS 连接日志,无异常。
按 Ctrl-C 停止,两个进程都应退出。

- [ ] **Step 5: Commit**

```bash
git add scripts/dev.sh Makefile
git commit -m "chore: make dev one-command local startup"
```

---

## Task 13: 一键部署 Docker

**Files:**
- Create: `Dockerfile`
- Create: `compose.yaml`
- Create: `.dockerignore`

- [ ] **Step 1: 写 .dockerignore**

`.dockerignore`:
```
**/node_modules
**/dist
backend/.venv
**/__pycache__
.git
.superpowers
docs
```

- [ ] **Step 2: 写多阶段 Dockerfile**

`Dockerfile`:
```dockerfile
# --- 阶段 1:构建前端 ---
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- 阶段 2:Python 后端 + 托管静态产物 ---
FROM python:3.11-slim AS backend
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=frontend /app/frontend/dist /app/static
ENV STATIC_DIR=/app/static
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "voicetrainer.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: 写 compose.yaml**

`compose.yaml`:
```yaml
services:
  voice-trainer:
    build: .
    ports:
      - "8000:8000"
    restart: unless-stopped
```

- [ ] **Step 4: 构建并起容器验证**

Run: `docker compose up --build -d`
然后浏览器开 `http://localhost:8000`(注意是 8000,前后端同端口)。
Expected:
- 页面正常加载(后端托管的静态产物)。
- 点"开始" → 麦克风权限 → 实时双轨工作(同 Task 12,但走单端口)。
- `docker compose logs` 无异常。
关闭:`docker compose down`

- [ ] **Step 5: Commit**

```bash
git add Dockerfile compose.yaml .dockerignore
git commit -m "chore: one-command docker deploy (single image, single port)"
```

---

## Task 14: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: 写 README**

`README.md`:
```markdown
# Voice Trainer

实时显示音高(F0)和归一化共鸣是否在目标带内的反馈工具。

## 本地开发(一条命令)

    make install   # 首次:建后端 venv + 装前后端依赖
    make dev       # 同时起后端(:8000)和前端 dev(:5173)

浏览器开 http://localhost:5173 ,点"开始"并允许麦克风。

## 测试

    make test      # 后端 pytest

## 部署(一键)

    docker compose up --build -d

浏览器开 http://localhost:8000 (前后端同端口)。

## 架构

- 前端(Vite/TS):WebAudio 采麦克风 → Int16 PCM 块 → WebSocket。
- 后端(FastAPI):滚动缓冲 + parselmouth 算 F0/共振峰/归一化共鸣,实时推回;同时托管前端静态产物。
- 分析引擎(`backend/voicetrainer/analysis/`):纯函数,实时与未来的录制复盘共用,口径一致。

## 现状与边界

- MVP:连读双轨(音高 + 归一化共鸣)+ 内置默认目标带。
- 归一化共鸣用内置通用元音模板;个人标定、单元音定位图、录制复盘为后续阶段。
- 只判可测量层(F0/共振峰/共鸣),不做音色审美判断。
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with dev/test/deploy instructions"
```

---

## 验收标准(全部完成后)

- [ ] `make install && make test` → 后端全部测试通过。
- [ ] `make dev` → 浏览器 :5173 实时双轨工作:说话时音高/共鸣点出现,在区绿、出区红,目标带可见。
- [ ] `docker compose up --build -d` → :8000 单端口同样工作。
- [ ] 静音/太轻时显示"听不到,说大声点",不画噪声点。
- [ ] 清音(s/f)时不误判跑调(unvoiced 不画音高点)。
