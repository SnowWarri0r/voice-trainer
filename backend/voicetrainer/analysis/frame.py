from dataclasses import asdict, dataclass
from typing import Optional

import numpy as np

from voicetrainer.analysis.formants import estimate_formants
from voicetrainer.analysis.pitch import estimate_f0
from voicetrainer.analysis.vowel import VOWEL_TEMPLATES, classify_vowel, normalized_resonance


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
