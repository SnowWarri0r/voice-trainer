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
