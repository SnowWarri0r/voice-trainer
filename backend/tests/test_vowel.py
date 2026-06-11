import math
from voicetrainer.analysis.vowel import (
    VOWEL_TEMPLATES,
    classify_vowel,
    normalized_resonance,
)


def test_classify_vowel_matches_nearest_template():
    # 贴近 "a" 模板 (700, 1220) 的输入应归为 "a"
    assert classify_vowel(710.0, 1230.0) == "a"
    # 贴近 "i" 模板 (320, 2200)
    assert classify_vowel(330.0, 2150.0) == "i"


def test_normalized_resonance_zero_at_template():
    # 正好等于模板共振峰时,抬升量为 0 个八度
    f1, f2 = VOWEL_TEMPLATES["a"]
    assert abs(normalized_resonance(f1, f2)) < 1e-9


def test_normalized_resonance_positive_when_brighter():
    # 共振峰整体抬高(更亮)→ 正值
    f1, f2 = VOWEL_TEMPLATES["a"]
    r = normalized_resonance(f1 * 1.2, f2 * 1.2)
    assert r > 0
    assert abs(r - math.log2(1.2)) < 1e-6


def test_resonance_is_vowel_independent_within_cells():
    # 同一个整体抬升,在不同元音上应给出同一个共鸣值 —— 前提是分类没翻格。
    expected = math.log2(1.15)
    for v in ("a", "e", "i", "u"):  # 'o' 故意排除:它在 1.15x 会翻格,见下一个测试
        t1, t2 = VOWEL_TEMPLATES[v]
        assert classify_vowel(t1 * 1.15, t2 * 1.15) == v
        assert abs(normalized_resonance(t1 * 1.15, t2 * 1.15) - expected) < 1e-9


def test_known_cell_flip_is_documented():
    # 回归守护:把 'o' 抬 1.15x 当前会被误分类成 'a'(已知 MVP 局限,阶段二修)。
    t1, t2 = VOWEL_TEMPLATES["o"]
    assert classify_vowel(t1 * 1.15, t2 * 1.15) == "a"


def test_classify_vowel_uses_passed_templates():
    custom = {"x": (500.0, 1500.0), "y": (300.0, 2500.0)}
    assert classify_vowel(510.0, 1490.0, custom) == "x"
    assert classify_vowel(310.0, 2450.0, custom) == "y"


def test_normalized_resonance_zero_at_passed_template():
    custom = {"x": (600.0, 1400.0)}
    assert abs(normalized_resonance(600.0, 1400.0, custom)) < 1e-9
