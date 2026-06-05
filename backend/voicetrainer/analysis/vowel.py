import math
from typing import Dict, Tuple

# 通用中性基线元音模板 (F1, F2),单位 Hz。MVP 用这套;阶段二替换为个人标定值。
VOWEL_TEMPLATES: Dict[str, Tuple[float, float]] = {
    "a": (700.0, 1220.0),
    "e": (530.0, 1840.0),
    "i": (320.0, 2200.0),
    "o": (570.0, 900.0),
    "u": (350.0, 800.0),
}


def _log_dist2(f1: float, f2: float, t1: float, t2: float) -> float:
    return (math.log2(f1 / t1)) ** 2 + (math.log2(f2 / t2)) ** 2


def classify_vowel(f1: float, f2: float) -> str:
    """在对数频率空间里取最近的元音模板。

    前提:f1, f2 必须是正数 Hz(调用方保证 —— formants.py 已把失败/NaN 归为 None,
    frame.py 只在两者非 None 时才调用本函数)。"""
    return min(
        VOWEL_TEMPLATES,
        key=lambda v: _log_dist2(f1, f2, *VOWEL_TEMPLATES[v]),
    )


def normalized_resonance(f1: float, f2: float) -> float:
    """相对最近元音模板,共振峰整体抬升了多少(单位:八度)。>0 = 更亮(共振峰偏高),<0 = 更暗(共振峰偏低)。

    前提:f1, f2 必须是正数 Hz(同 classify_vowel)。

    MVP 局限:此值仅在「最近元音格子」内对换元音不变。整体抬升 ≳0.18 八度时,
    被抬高的共振峰可能越过 Voronoi 边界翻到相邻元音格(例:把 'o' 抬 ~1.15x 会被判成 'a'),
    导致结果符号反转。大幅调整共振峰的目标幅度恰在此范围,故连读/大幅抬升时此值可能失真。
    真正的修法(让分类对整体抬升不变)属阶段二;见 test_known_cell_flip_is_documented。"""
    vowel = classify_vowel(f1, f2)
    t1, t2 = VOWEL_TEMPLATES[vowel]
    return 0.5 * (math.log2(f1 / t1) + math.log2(f2 / t2))
