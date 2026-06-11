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
    assert analyze_vowel_recording(np.zeros(int(sr * 0.01), dtype=np.float32), sr) is None
