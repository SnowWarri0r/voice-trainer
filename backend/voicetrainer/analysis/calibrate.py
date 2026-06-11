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
