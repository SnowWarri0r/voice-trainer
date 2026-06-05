from voicetrainer.targets import TargetProfile, builtin_default


def test_builtin_default_fields():
    t = builtin_default()
    assert t.source == "builtin"
    assert t.f0_min < t.f0_max
    assert t.resonance_min < t.resonance_max


def test_contains_in_target():
    t = builtin_default()
    mid_f0 = (t.f0_min + t.f0_max) / 2
    mid_res = (t.resonance_min + t.resonance_max) / 2
    r = t.contains(mid_f0, mid_res)
    assert r == {"f0_in": True, "resonance_in": True, "in_target": True}


def test_contains_out_of_target():
    t = builtin_default()
    r = t.contains(t.f0_min - 50, t.resonance_min - 1.0)
    assert r["in_target"] is False
    assert r["f0_in"] is False


def test_contains_handles_none():
    t = builtin_default()
    r = t.contains(None, None)
    assert r == {"f0_in": False, "resonance_in": False, "in_target": False}
