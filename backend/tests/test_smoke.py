import numpy as np
import parselmouth


def test_deps_importable():
    snd = parselmouth.Sound(np.zeros(1000, dtype=np.float64), sampling_frequency=16000)
    assert snd.duration > 0
