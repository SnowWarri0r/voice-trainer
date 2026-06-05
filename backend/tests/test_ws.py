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
