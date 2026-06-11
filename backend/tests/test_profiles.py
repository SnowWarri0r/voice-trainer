from voicetrainer.profiles import Profile, load_active, save
from voicetrainer.targets import builtin_default


def test_load_active_no_file_returns_builtin(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILE_PATH", str(tmp_path / "profile.json"))
    p = load_active()
    assert p.source == "builtin"
    assert set(p.vowel_templates.keys()) == {"a", "e", "i", "o", "u"}


def test_save_then_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILE_PATH", str(tmp_path / "profile.json"))
    templates = {"a": [710.0, 1180.0], "e": [540.0, 1800.0], "i": [330.0, 2150.0],
                 "o": [560.0, 920.0], "u": [360.0, 820.0]}
    save(Profile(vowel_templates=templates, target=builtin_default(), source="calibrated"))
    p = load_active()
    assert p.source == "calibrated"
    assert p.vowel_templates["a"] == [710.0, 1180.0]
    assert p.target.f0_min == builtin_default().f0_min


def test_load_active_corrupt_file_returns_builtin(tmp_path, monkeypatch):
    path = tmp_path / "profile.json"
    path.write_text("{ not valid json")
    monkeypatch.setenv("PROFILE_PATH", str(path))
    p = load_active()
    assert p.source == "builtin"
