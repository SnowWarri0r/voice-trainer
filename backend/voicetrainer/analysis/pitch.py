from typing import Optional

import numpy as np
import parselmouth


def estimate_f0(
    samples: np.ndarray,
    sample_rate: int,
    fmin: float = 75.0,
    fmax: float = 500.0,
) -> Optional[float]:
    """估计一段单声道 PCM 的基频(Hz)。无声/清音返回 None。"""
    if samples.size == 0 or float(np.max(np.abs(samples))) < 1e-4:
        return None
    snd = parselmouth.Sound(samples.astype(np.float64), sampling_frequency=sample_rate)
    try:
        pitch = snd.to_pitch(pitch_floor=fmin, pitch_ceiling=fmax)
    except Exception:
        return None
    freqs = pitch.selected_array["frequency"]
    voiced = freqs[freqs > 0]
    if voiced.size == 0:
        return None
    return float(np.median(voiced))
