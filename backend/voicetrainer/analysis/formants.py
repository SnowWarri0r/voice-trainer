from typing import Optional, Tuple

import numpy as np
import parselmouth


def estimate_formants(
    samples: np.ndarray,
    sample_rate: int,
    max_formant: float = 5500.0,
) -> Tuple[Optional[float], Optional[float]]:
    """估计 (F1, F2),单位 Hz。取信号中点处的共振峰值。无声/失败返回 (None, None)。"""
    if samples.size == 0 or float(np.max(np.abs(samples))) < 1e-4:
        return (None, None)
    snd = parselmouth.Sound(samples.astype(np.float64), sampling_frequency=sample_rate)
    try:
        formant = snd.to_formant_burg(maximum_formant=max_formant)
    except Exception:
        return (None, None)
    t = snd.duration / 2.0
    f1 = formant.get_value_at_time(1, t)
    f2 = formant.get_value_at_time(2, t)
    f1 = None if (f1 is None or np.isnan(f1)) else float(f1)
    f2 = None if (f2 is None or np.isnan(f2)) else float(f2)
    return (f1, f2)
