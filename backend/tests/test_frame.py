import numpy as np
from voicetrainer.analysis.frame import AnalysisResult, analyze_frame


def _voiced_vowel(f0, f_a, f_b, dur, sr):
    t = np.arange(int(sr * dur)) / sr
    sig = 0.4 * np.sin(2 * np.pi * f0 * t)
    sig += 0.3 * np.sin(2 * np.pi * f_a * t)
    sig += 0.3 * np.sin(2 * np.pi * f_b * t)
    return sig.astype(np.float32)


def _whispered_vowel(f_a, f_b, dur, sr, bandwidths=(250.0, 300.0), amp=0.6, seed=0):
    """气声/耳语合成:噪声激励(无周期性,故无 F0)过宽带共振峰谐振器,得到有共振峰、无音高的信号。
    带宽取得宽(真耳语共振峰带宽本就宽),避免窄带振铃被误判出伪音高。"""
    rng = np.random.default_rng(seed)
    y = rng.standard_normal(int(sr * dur))
    for f, b in zip((f_a, f_b), bandwidths):
        r = np.exp(-np.pi * b / sr)
        theta = 2.0 * np.pi * f / sr
        a1 = -2.0 * r * np.cos(theta)
        a2 = r * r
        out = np.zeros_like(y)
        for i in range(len(y)):
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


def test_analyze_frame_silence_is_unvoiced():
    sr = 16000
    res = analyze_frame(np.zeros(int(sr * 0.2), dtype=np.float32), sr)
    assert isinstance(res, AnalysisResult)
    assert res.voiced is False
    assert res.f0 is None


def test_analyze_frame_voiced_has_all_fields():
    sr = 16000
    res = analyze_frame(_voiced_vowel(200.0, 800.0, 1200.0, 0.2, sr), sr)
    assert res.voiced is True
    assert res.f0 is not None and abs(res.f0 - 200.0) < 8.0
    assert res.f1 is not None and res.f2 is not None
    assert res.vowel in {"a", "e", "i", "o", "u"}
    assert res.resonance is not None


def test_analyze_frame_breathy_has_resonance_without_pitch():
    # 气声:无 F0(voiced=False),但共振峰/共鸣仍应输出 —— 这是共鸣训练能在气声上做的关键。
    sr = 16000
    res = analyze_frame(_whispered_vowel(700.0, 1200.0, 0.3, sr), sr)
    assert res.voiced is False
    assert res.f0 is None
    assert res.f1 is not None and res.f2 is not None
    assert res.resonance is not None
    assert res.vowel in {"a", "e", "i", "o", "u"}


def test_to_dict_roundtrip_keys():
    res = analyze_frame(np.zeros(1000, dtype=np.float32), 16000)
    d = res.to_dict()
    assert set(d.keys()) == {"voiced", "f0", "f1", "f2", "vowel", "resonance"}


def test_analyze_frame_uses_passed_templates():
    sr = 16000
    sig = _voiced_vowel(200.0, 800.0, 1200.0, 0.2, sr)
    base = analyze_frame(sig, sr)
    assert base.f1 is not None and base.f2 is not None
    # 以实测共振峰为中心的个人模板 → 该帧共鸣应 ≈ 0
    custom = {base.vowel: (base.f1, base.f2)}
    res = analyze_frame(sig, sr, templates=custom)
    assert res.resonance is not None and abs(res.resonance) < 1e-6
