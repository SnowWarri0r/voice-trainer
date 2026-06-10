# Voice Trainer — Personal Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户录自己的 5 个元音建个人模板,替换内置通用模板,使分类更准、共鸣数 = 相对自己基线的抬升,并持久化为激活 profile 供实时反馈使用。

**Architecture:** 分析层纯函数加 `templates` 参数(默认内置,老调用不变);新增 `analyze_vowel_recording`(整段 clip 取共振峰中位数)和 `profiles.py`(Profile 模型 + 本地 JSON 持久化,无文件回退内置);后端加 calibrate/profile 端点,WS 连接时加载激活 profile 并透传模板;前端加引导式标定流。

**Tech Stack:** Python 3.12 / FastAPI / numpy / praat-parselmouth / pytest;TypeScript / Vite。

**约定:** 仓库本地 git 身份已正确(`SnowWarri0r <gerrytranchina@gmail.com>`),一律 PLAIN `git commit`,绝不用 `-c` 覆盖或任何 work email。后端命令在 `backend/` 下激活 venv:`. .venv/bin/activate`。当前基线:全套 `pytest -q` = 21 passed。

---

## File Structure

```
backend/voicetrainer/
  analysis/
    vowel.py          # 改:classify_vowel / normalized_resonance 加 templates 参数
    frame.py          # 改:analyze_frame 加 templates 参数,透传
    calibrate.py      # 新:analyze_vowel_recording
  profiles.py         # 新:Profile 模型 + load_active / save(本地 JSON)
  app.py              # 改:/api/profile GET/PUT, /api/calibrate POST, /api/target 改读 active, WS 透传模板
backend/tests/
  test_vowel.py       # 改:加 templates 参数测试
  test_frame.py       # 改:加 templates 透传测试
  test_calibrate.py   # 新
  test_profiles.py    # 新
  test_profile_api.py # 新:端点
frontend/
  index.html          # 改:加 Calibrate 按钮
  src/calibrate.ts    # 新:录 clip + 引导标定流
  src/main.ts         # 改:接 Calibrate 按钮
.gitignore            # 改:加 backend/data/
```

---

## Task 1: 分析层加 templates 参数(vowel + frame)

**Files:**
- Modify: `backend/voicetrainer/analysis/vowel.py`
- Modify: `backend/voicetrainer/analysis/frame.py`
- Test: `backend/tests/test_vowel.py`, `backend/tests/test_frame.py`

- [ ] **Step 1: 写失败测试(vowel)**

在 `backend/tests/test_vowel.py` 末尾追加:
```python
def test_classify_vowel_uses_passed_templates():
    custom = {"x": (500.0, 1500.0), "y": (300.0, 2500.0)}
    assert classify_vowel(510.0, 1490.0, custom) == "x"
    assert classify_vowel(310.0, 2450.0, custom) == "y"


def test_normalized_resonance_zero_at_passed_template():
    custom = {"x": (600.0, 1400.0)}
    assert abs(normalized_resonance(600.0, 1400.0, custom)) < 1e-9
```

- [ ] **Step 2: 写失败测试(frame)**

在 `backend/tests/test_frame.py` 末尾追加:
```python
def test_analyze_frame_uses_passed_templates():
    sr = 16000
    sig = _voiced_vowel(200.0, 800.0, 1200.0, 0.2, sr)
    base = analyze_frame(sig, sr)
    assert base.f1 is not None and base.f2 is not None
    # 以实测共振峰为中心的个人模板 → 该帧共鸣应 ≈ 0
    custom = {base.vowel: (base.f1, base.f2)}
    res = analyze_frame(sig, sr, templates=custom)
    assert res.resonance is not None and abs(res.resonance) < 1e-6
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_vowel.py tests/test_frame.py -q`
Expected: FAIL — `classify_vowel`/`normalized_resonance`/`analyze_frame` got unexpected positional/keyword arg (TypeError)。

- [ ] **Step 4: 改 vowel.py**

把 `classify_vowel` 和 `normalized_resonance` 改为(其余不动):
```python
def classify_vowel(f1: float, f2: float, templates: Dict[str, Tuple[float, float]] = VOWEL_TEMPLATES) -> str:
    """在对数频率空间里取最近的元音模板(默认内置,可传个人标定模板)。

    前提:f1, f2 必须是正数 Hz(调用方保证 —— formants.py 已把失败/NaN 归为 None,
    frame.py 只在两者非 None 时才调用本函数)。"""
    return min(templates, key=lambda v: _log_dist2(f1, f2, *templates[v]))


def normalized_resonance(f1: float, f2: float, templates: Dict[str, Tuple[float, float]] = VOWEL_TEMPLATES) -> float:
    """相对最近元音模板,共振峰整体抬升了多少(单位:八度)。>0 = 更亮(共振峰偏高),<0 = 更暗(共振峰偏低)。

    前提:f1, f2 必须是正数 Hz(同 classify_vowel)。

    MVP 局限:此值仅在「最近元音格子」内对换元音不变。整体抬升 ≳0.18 八度时,
    被抬高的共振峰可能越过 Voronoi 边界翻到相邻元音格(例:把 'o' 抬 ~1.15x 会被判成 'a'),
    导致结果符号反转。大幅调整共振峰的目标幅度恰在此范围,故连读/大幅抬升时此值可能失真。
    真正的修法(让分类对整体抬升不变)属后续;见 test_known_cell_flip_is_documented。"""
    vowel = classify_vowel(f1, f2, templates)
    t1, t2 = templates[vowel]
    return 0.5 * (math.log2(f1 / t1) + math.log2(f2 / t2))
```

- [ ] **Step 5: 改 frame.py**

把 import 行改为:
```python
from voicetrainer.analysis.vowel import VOWEL_TEMPLATES, classify_vowel, normalized_resonance
```
把 `analyze_frame` 签名与调用改为:
```python
def analyze_frame(samples: np.ndarray, sample_rate: int, templates=VOWEL_TEMPLATES) -> AnalysisResult:
    """一段 PCM → 完整分析结果。

    voiced 反映是否测到基频(声带振动);共振峰/共鸣**不**依赖 voiced——
    气声/耳语没有 F0 但仍有共振峰,照样输出 resonance,这样共鸣训练能在气声上做。
    纯静音(共振峰也测不到)则只返回 voiced=False。
    templates 默认内置;传入个人标定模板可让分类/共鸣贴合用户声道。"""
    f0 = estimate_f0(samples, sample_rate)
    f1, f2 = estimate_formants(samples, sample_rate)
    voiced = f0 is not None
    if f1 is None or f2 is None:
        return AnalysisResult(voiced=voiced, f0=f0)
    return AnalysisResult(
        voiced=voiced,
        f0=f0,
        f1=f1,
        f2=f2,
        vowel=classify_vowel(f1, f2, templates),
        resonance=normalized_resonance(f1, f2, templates),
    )
```

- [ ] **Step 6: 跑测试确认通过 + 无回归**

Run: `cd backend && . .venv/bin/activate && pytest -q`
Expected: 24 passed(原 21 + 新 3:2 个 vowel + 1 个 frame)。

- [ ] **Step 7: Commit**

```bash
git add backend/voicetrainer/analysis/vowel.py backend/voicetrainer/analysis/frame.py backend/tests/test_vowel.py backend/tests/test_frame.py
git commit -m "feat: thread per-user vowel templates through analysis (default builtin)"
```

---

## Task 2: 标定提取 `analyze_vowel_recording`

**Files:**
- Create: `backend/voicetrainer/analysis/calibrate.py`
- Test: `backend/tests/test_calibrate.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_calibrate.py`:
```python
import numpy as np
from voicetrainer.analysis.calibrate import analyze_vowel_recording


def _sustained_vowel(f0, formants, dur, sr, bandwidths=(80.0, 90.0), amp=0.9):
    # 源-滤波器合成:F0 冲激串过两个共振峰谐振器,得到 voiced 且有共振峰的持续元音。
    n = int(sr * dur)
    src = np.zeros(n, dtype=np.float64)
    period = max(1, int(sr / f0))
    src[::period] = 1.0
    y = src
    for f, b in zip(formants, bandwidths):
        r = np.exp(-np.pi * b / sr)
        theta = 2.0 * np.pi * f / sr
        a1 = -2.0 * r * np.cos(theta)
        a2 = r * r
        out = np.zeros(n, dtype=np.float64)
        for i in range(n):
            x = y[i]
            if i >= 1:
                x -= a1 * out[i - 1]
            if i >= 2:
                x -= a2 * out[i - 2]
            out[i] = x
        y = out
    peak = float(np.max(np.abs(y)))
    if peak > 0:
        y = y / peak * amp
    return y.astype(np.float32)


def test_analyze_vowel_recording_returns_median_formants():
    sr = 16000
    sig = _sustained_vowel(120.0, [700.0, 1200.0], 1.0, sr)
    res = analyze_vowel_recording(sig, sr)
    assert res is not None
    f1, f2 = res
    assert abs(f1 - 700.0) < 150.0
    assert abs(f2 - 1200.0) < 150.0


def test_analyze_vowel_recording_silence_returns_none():
    sr = 16000
    assert analyze_vowel_recording(np.zeros(sr, dtype=np.float32), sr) is None


def test_analyze_vowel_recording_too_short_returns_none():
    sr = 16000
    # 短于一个分析窗
    assert analyze_vowel_recording(np.zeros(int(sr * 0.01), dtype=np.float32), sr) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_calibrate.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'voicetrainer.analysis.calibrate'`

- [ ] **Step 3: 写实现**

`backend/voicetrainer/analysis/calibrate.py`:
```python
from statistics import median
from typing import Optional, Tuple

import numpy as np

from voicetrainer.analysis.formants import estimate_formants
from voicetrainer.analysis.pitch import estimate_f0

WINDOW_MS = 75
MIN_VALID_RATIO = 0.30
MIN_VALID_WINDOWS = 5


def analyze_vowel_recording(samples: np.ndarray, sample_rate: int) -> Optional[Tuple[float, float]]:
    """对一段持续元音 clip 取共振峰中位数 → (F1, F2)。
    有效窗(voiced 且 F1/F2 都有)太少则返回 None(让用户重录)。"""
    win = int(sample_rate * WINDOW_MS / 1000)
    if win <= 0 or samples.size < win:
        return None
    f1s = []
    f2s = []
    n_windows = 0
    for start in range(0, samples.size - win + 1, win):
        w = samples[start:start + win]
        n_windows += 1
        if estimate_f0(w, sample_rate) is None:
            continue
        a, b = estimate_formants(w, sample_rate)
        if a is None or b is None:
            continue
        f1s.append(a)
        f2s.append(b)
    if n_windows == 0:
        return None
    if len(f1s) < MIN_VALID_WINDOWS or len(f1s) < MIN_VALID_RATIO * n_windows:
        return None
    return (float(median(f1s)), float(median(f2s)))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_calibrate.py -q`
Expected: 3 passed
(若 `test_...returns_median_formants` 因合成元音 F1/F2 略超 ±150 容差,放宽到 ±200 并在测试注释说明——这层只需保证中位数落在合理范围,不追求精确。不要改实现去迁就测试。)

- [ ] **Step 5: Commit**

```bash
git add backend/voicetrainer/analysis/calibrate.py backend/tests/test_calibrate.py
git commit -m "feat: analyze_vowel_recording for calibration (median formants of a clip)"
```

---

## Task 3: Profile 模型 + 持久化 `profiles.py`

**Files:**
- Create: `backend/voicetrainer/profiles.py`
- Test: `backend/tests/test_profiles.py`
- Modify: `.gitignore`

- [ ] **Step 1: gitignore 用户数据**

在 `.gitignore` 末尾追加一行:
```
backend/data/
```

- [ ] **Step 2: 写失败测试**

`backend/tests/test_profiles.py`:
```python
from voicetrainer.profiles import Profile, load_active, save
from voicetrainer.targets import builtin_default


def test_load_active_no_file_returns_builtin(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILE_PATH", str(tmp_path / "profile.json"))
    p = load_active()
    assert p.source == "builtin"
    assert set(p.vowel_templates.keys()) == {"a", "e", "i", "o", "u"}


def test_save_then_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILE_PATH", str(tmp_path / "profile.json"))
    templates = {"a": [710.0, 1180.0], "e": [540.0, 1800.0], "i": [330.0, 2150.0],
                 "o": [560.0, 920.0], "u": [360.0, 820.0]}
    save(Profile(vowel_templates=templates, target=builtin_default(), source="calibrated"))
    p = load_active()
    assert p.source == "calibrated"
    assert p.vowel_templates["a"] == [710.0, 1180.0]
    assert p.target.f0_min == builtin_default().f0_min


def test_load_active_corrupt_file_returns_builtin(tmp_path, monkeypatch):
    path = tmp_path / "profile.json"
    path.write_text("{ not valid json")
    monkeypatch.setenv("PROFILE_PATH", str(path))
    p = load_active()
    assert p.source == "builtin"
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_profiles.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'voicetrainer.profiles'`

- [ ] **Step 4: 写实现**

`backend/voicetrainer/profiles.py`:
```python
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from typing import Dict, List

from voicetrainer.analysis.vowel import VOWEL_TEMPLATES
from voicetrainer.targets import TargetProfile, builtin_default

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "profile.json")


@dataclass
class Profile:
    vowel_templates: Dict[str, List[float]]
    target: TargetProfile
    source: str = "builtin"

    def to_dict(self) -> dict:
        return {
            "vowel_templates": self.vowel_templates,
            "target": asdict(self.target),
            "source": self.source,
        }


def _profile_path() -> str:
    return os.environ.get("PROFILE_PATH", DEFAULT_PATH)


def _builtin_profile() -> Profile:
    return Profile(
        vowel_templates={k: [v[0], v[1]] for k, v in VOWEL_TEMPLATES.items()},
        target=builtin_default(),
        source="builtin",
    )


def load_active() -> Profile:
    """读激活 profile;无文件/损坏则回退内置(不抛异常)。"""
    path = _profile_path()
    try:
        with open(path) as f:
            data = json.load(f)
        templates = {k: [float(x) for x in v] for k, v in data["vowel_templates"].items()}
        target = TargetProfile(**data["target"])
        return Profile(vowel_templates=templates, target=target, source=data.get("source", "calibrated"))
    except (FileNotFoundError, KeyError, ValueError, TypeError, json.JSONDecodeError):
        return _builtin_profile()


def save(profile: Profile) -> None:
    """原子写 JSON(先写临时文件再 rename)。"""
    path = _profile_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(profile.to_dict(), f)
    os.replace(tmp, path)
```

- [ ] **Step 5: 跑测试确认通过 + 无回归**

Run: `cd backend && . .venv/bin/activate && pytest -q`
Expected: 全部 passed(30 = 24 + 3(calibrate)+ 3(profiles))。

- [ ] **Step 6: Commit**

```bash
git add backend/voicetrainer/profiles.py backend/tests/test_profiles.py .gitignore
git commit -m "feat: Profile model with JSON persistence and builtin fallback"
```

---

## Task 4: 端点 + WS 透传激活 profile

**Files:**
- Modify: `backend/voicetrainer/app.py`
- Test: `backend/tests/test_profile_api.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_profile_api.py`:
```python
import json

import numpy as np
from fastapi.testclient import TestClient

from voicetrainer.app import app


def _sustained_vowel(f0, formants, dur, sr, bandwidths=(80.0, 90.0), amp=0.9):
    n = int(sr * dur)
    src = np.zeros(n, dtype=np.float64)
    period = max(1, int(sr / f0))
    src[::period] = 1.0
    y = src
    for f, b in zip(formants, bandwidths):
        r = np.exp(-np.pi * b / sr)
        theta = 2.0 * np.pi * f / sr
        a1 = -2.0 * r * np.cos(theta)
        a2 = r * r
        out = np.zeros(n, dtype=np.float64)
        for i in range(n):
            x = y[i]
            if i >= 1:
                x -= a1 * out[i - 1]
            if i >= 2:
                x -= a2 * out[i - 2]
            out[i] = x
        y = out
    peak = float(np.max(np.abs(y)))
    if peak > 0:
        y = y / peak * amp
    return (y * 32767).astype("<i2").tobytes()


def test_get_profile_default_is_builtin(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILE_PATH", str(tmp_path / "profile.json"))
    client = TestClient(app)
    body = client.get("/api/profile").json()
    assert body["source"] == "builtin"
    assert set(body["vowel_templates"].keys()) == {"a", "e", "i", "o", "u"}


def test_put_then_get_profile_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILE_PATH", str(tmp_path / "profile.json"))
    client = TestClient(app)
    templates = {"a": [710.0, 1180.0], "e": [540.0, 1800.0], "i": [330.0, 2150.0],
                 "o": [560.0, 920.0], "u": [360.0, 820.0]}
    r = client.put("/api/profile", json={"vowel_templates": templates})
    assert r.status_code == 200
    assert r.json()["source"] == "calibrated"
    got = client.get("/api/profile").json()
    assert got["source"] == "calibrated"
    assert got["vowel_templates"]["a"] == [710.0, 1180.0]


def test_put_profile_missing_vowel_is_400(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILE_PATH", str(tmp_path / "profile.json"))
    client = TestClient(app)
    r = client.put("/api/profile", json={"vowel_templates": {"a": [710.0, 1180.0]}})
    assert r.status_code == 400


def test_calibrate_returns_formants_for_vowel_clip():
    client = TestClient(app)
    sr = 16000
    clip = _sustained_vowel(120.0, [700.0, 1200.0], 1.0, sr)
    r = client.post(f"/api/calibrate?vowel=a&sampleRate={sr}", content=clip)
    assert r.status_code == 200
    body = r.json()
    assert "f1" in body and "f2" in body
    assert abs(body["f1"] - 700.0) < 200.0


def test_calibrate_silence_returns_retake():
    client = TestClient(app)
    sr = 16000
    silence = np.zeros(sr, dtype="<i2").tobytes()
    r = client.post(f"/api/calibrate?vowel=a&sampleRate={sr}", content=silence)
    assert r.json() == {"retake": True}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_profile_api.py -q`
Expected: FAIL — 端点不存在(404),import 或断言失败。

- [ ] **Step 3: 改 app.py**

把顶部 import 区改为(在现有 import 基础上增加):
```python
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
```
把 `/api/target` 改为读激活 profile:
```python
@app.get("/api/target")
def target() -> dict:
    return asdict(load_active().target)
```
新增三个端点(放在 `/api/target` 之后、`/ws` 之前):
```python
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
```
把 WS 循环里加载 profile 并透传(在 `await websocket.accept()` 之后,把原来的 `profile = builtin_default()` 那行替换):
```python
    await websocket.accept()
    profile = load_active()
    sample_rate = 48000
    buf = np.zeros(0, dtype=np.float32)
```
并把分析与判定两行改为:
```python
            result = analyze_frame(buf, sample_rate, templates=profile.vowel_templates)
            payload = result.to_dict()
            payload.update(profile.target.contains(result.f0, result.resonance))
```
(删掉原来对 `builtin_default()` 的直接引用;`builtin_default` 现仍被 `put_profile` 用到,保留 import。)

- [ ] **Step 4: 跑测试确认通过 + 无回归**

Run: `cd backend && . .venv/bin/activate && pytest -q`
Expected: 全部 passed(35 = 30 + 5(profile_api))。

- [ ] **Step 5: Commit**

```bash
git add backend/voicetrainer/app.py backend/tests/test_profile_api.py
git commit -m "feat: calibrate/profile endpoints; WS uses active profile templates"
```

---

## Task 5: 前端引导式标定流

**Files:**
- Modify: `frontend/index.html`
- Create: `frontend/src/calibrate.ts`
- Modify: `frontend/src/main.ts`

> 麦克风/UI 无单测,走 `npx tsc --noEmit` + 手动冒烟。

- [ ] **Step 1: index.html 加按钮**

把 `frontend/index.html` 的按钮行从:
```html
      <button id="start">开始</button>
```
改为:
```html
      <button id="start">开始</button>
      <button id="calibrate">标定</button>
```

- [ ] **Step 2: 写 calibrate.ts**

`frontend/src/calibrate.ts`:
```typescript
// 录一段定长 clip(Int16 PCM),返回字节与采样率。
async function recordClip(seconds: number): Promise<{ pcm: ArrayBuffer; sampleRate: number }> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
  });
  const ctx = new AudioContext();
  if (ctx.state === "suspended") await ctx.resume();
  const source = ctx.createMediaStreamSource(stream);
  const proc = ctx.createScriptProcessor(2048, 1, 1);
  const mute = ctx.createGain();
  mute.gain.value = 0;
  const chunks: Int16Array[] = [];
  proc.onaudioprocess = (e) => {
    const f32 = e.inputBuffer.getChannelData(0);
    const i16 = new Int16Array(f32.length);
    for (let i = 0; i < f32.length; i++) {
      const s = Math.max(-1, Math.min(1, f32[i]));
      i16[i] = Math.round(s * 32767);
    }
    chunks.push(i16);
  };
  source.connect(proc);
  proc.connect(mute);
  mute.connect(ctx.destination);

  await new Promise((r) => setTimeout(r, seconds * 1000));

  proc.disconnect();
  source.disconnect();
  mute.disconnect();
  const sampleRate = ctx.sampleRate;
  await ctx.close();
  stream.getTracks().forEach((t) => t.stop());

  const total = chunks.reduce((n, c) => n + c.length, 0);
  const merged = new Int16Array(total);
  let off = 0;
  for (const c of chunks) {
    merged.set(c, off);
    off += c.length;
  }
  return { pcm: merged.buffer, sampleRate };
}

interface CalibResult {
  f1?: number;
  f2?: number;
  retake?: boolean;
}

async function calibrateOne(vowel: string, pcm: ArrayBuffer, sampleRate: number): Promise<CalibResult> {
  const r = await fetch(`/api/calibrate?vowel=${vowel}&sampleRate=${sampleRate}`, {
    method: "POST",
    body: pcm,
  });
  return r.json();
}

const VOWELS: { id: string; prompt: string }[] = [
  { id: "a", prompt: "啊(像 spa)" },
  { id: "e", prompt: "诶" },
  { id: "i", prompt: "衣" },
  { id: "o", prompt: "喔" },
  { id: "u", prompt: "呜" },
];

// 跑完整标定流;onStatus 用于把进度/提示显示给用户。成功返回 true。
export async function runCalibration(onStatus: (msg: string) => void): Promise<boolean> {
  const templates: Record<string, [number, number]> = {};
  for (let i = 0; i < VOWELS.length; i++) {
    const { id, prompt } = VOWELS[i];
    let ok = false;
    for (let attempt = 0; attempt < 3 && !ok; attempt++) {
      onStatus(`标定 ${i + 1}/5:拉长发「${prompt}」… 录音中`);
      const { pcm, sampleRate } = await recordClip(2.5);
      const res = await calibrateOne(id, pcm, sampleRate);
      if (res.retake || typeof res.f1 !== "number" || typeof res.f2 !== "number") {
        onStatus(`没录到稳定的「${prompt}」,再来一次…`);
        await new Promise((r) => setTimeout(r, 700));
        continue;
      }
      templates[id] = [res.f1, res.f2];
      ok = true;
      onStatus(`「${prompt}」✓ (F1 ${res.f1.toFixed(0)} · F2 ${res.f2.toFixed(0)})`);
      await new Promise((r) => setTimeout(r, 500));
    }
    if (!ok) {
      onStatus(`「${prompt}」多次未录到稳定元音,标定中止。`);
      return false;
    }
  }
  const r = await fetch("/api/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vowel_templates: templates }),
  });
  if (!r.ok) {
    onStatus("保存个人模板失败。");
    return false;
  }
  onStatus("标定完成 ✓ 点「开始」即用个人模板。");
  return true;
}
```

- [ ] **Step 3: 接 main.ts**

在 `frontend/src/main.ts` 顶部 import 区加:
```typescript
import { runCalibration } from "./calibrate";
```
在文件中(`startBtn` 等获取之后、`loop()` 之前)加 Calibrate 按钮接线:
```typescript
const calibrateBtn = document.getElementById("calibrate") as HTMLButtonElement;

calibrateBtn.addEventListener("click", async () => {
  if (stop) {
    stop();
    stop = null;
    startBtn.textContent = "开始";
  }
  calibrateBtn.disabled = true;
  startBtn.disabled = true;
  try {
    await runCalibration((msg) => {
      statusEl.textContent = msg;
    });
    await loadTarget();
  } catch (e) {
    statusEl.textContent = "标定出错,请检查麦克风权限。";
  } finally {
    calibrateBtn.disabled = false;
    startBtn.disabled = false;
  }
});
```

- [ ] **Step 4: 类型检查 + 构建**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: 0 type errors,`frontend/dist/` 生成。

- [ ] **Step 5: 手动冒烟(需人工)**

启动 `make dev`,浏览器开 http://localhost:5173 ,点「标定」:
- 依次提示「拉长发 啊/诶/衣/喔/呜… 录音中」,每个录 2.5s。
- 每个元音录完显示 `✓ (F1 … F2 …)`;录不到稳定元音时提示重录。
- 5 个走完显示「标定完成 ✓」。
- 点「开始」,实时反馈现在用个人模板(共鸣相对你自己的元音基线)。
- `curl -s http://localhost:8000/api/profile` 应显示 `"source":"calibrated"` 且 5 个 vowel_templates 为你录的值。
- `backend/data/profile.json` 存在且不被 git 跟踪(`git status` 不显示它)。

- [ ] **Step 6: Commit**

```bash
git add frontend/index.html frontend/src/calibrate.ts frontend/src/main.ts
git commit -m "feat: guided 5-vowel calibration flow in frontend"
```

---

## 验收标准(全部完成后)

- [ ] 全套后端 `pytest -q` 通过(35 passed)。
- [ ] `npx tsc --noEmit && npm run build` 前端无错。
- [ ] 标定流:点「标定」→ 录 5 元音 → `/api/profile` 返回 `source:"calibrated"` + 5 模板。
- [ ] 标定后点「开始」,WS 用个人模板(实时共鸣以你自己的元音为基线)。
- [ ] 未标定时一切照旧(`load_active` 回退内置,实时反馈与之前一致)。
- [ ] `backend/data/profile.json` 已 gitignore,不进仓。
