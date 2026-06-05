import numpy as np
from voicetrainer.analysis.formants import estimate_formants


def _vowel(f0, formants, dur, sr, bandwidths=(80.0, 90.0), amp=0.9):
    """源-滤波器合成一个元音:F0 冲激串(声门源)级联过若干二阶共振峰谐振器。
    产生有真实共振峰带宽结构的语音样信号,LPC 能准确还原。"""
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


def test_estimate_formants_on_synthetic_vowel():
    sr = 16000
    # 合成一个 F1=700, F2=1200 的元音(类 /a/),F0=120Hz
    sig = _vowel(120.0, [700.0, 1200.0], 0.3, sr)
    f1, f2 = estimate_formants(sig, sr)
    assert f1 is not None and f2 is not None
    assert f1 < f2
    assert abs(f1 - 700.0) < 150.0
    assert abs(f2 - 1200.0) < 150.0


def test_estimate_formants_on_silence_returns_none():
    sr = 16000
    assert estimate_formants(np.zeros(int(sr * 0.2), dtype=np.float32), sr) == (None, None)
