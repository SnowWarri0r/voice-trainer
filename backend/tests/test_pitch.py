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
