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
    res = analyze_frame(_voiced_vowel(200.0, 800.0, 1200.0, 0.2, sr), sr)
    assert res.voiced is True
    assert res.f0 is not None and abs(res.f0 - 200.0) < 8.0
    assert res.f1 is not None and res.f2 is not None
    assert res.vowel in {"a", "e", "i", "o", "u"}
    assert res.resonance is not None


def test_to_dict_roundtrip_keys():
    res = analyze_frame(np.zeros(1000, dtype=np.float32), 16000)
    d = res.to_dict()
    assert set(d.keys()) == {"voiced", "f0", "f1", "f2", "vowel", "resonance"}
