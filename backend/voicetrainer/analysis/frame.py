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
