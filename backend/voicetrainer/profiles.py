import json
import os
import tempfile
from dataclasses import asdict, dataclass
from typing import Dict, List

from voicetrainer.analysis.vowel import VOWEL_TEMPLATES
from voicetrainer.targets import TargetProfile, builtin_default

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "profile.json")


@dataclass
class Profile:
    vowel_templates: Dict[str, List[float]]
    target: TargetProfile
    source: str = "builtin"

    def to_dict(self) -> dict:
        return {
            "vowel_templates": self.vowel_templates,
            "target": asdict(self.target),
            "source": self.source,
        }


def _profile_path() -> str:
    return os.environ.get("PROFILE_PATH", DEFAULT_PATH)


def _builtin_profile() -> Profile:
    return Profile(
        vowel_templates={k: [v[0], v[1]] for k, v in VOWEL_TEMPLATES.items()},
        target=builtin_default(),
        source="builtin",
    )


def load_active() -> Profile:
    """读激活 profile;无文件/损坏则回退内置(不抛异常)。"""
    path = _profile_path()
    try:
        with open(path) as f:
            data = json.load(f)
        templates = {k: [float(x) for x in v] for k, v in data["vowel_templates"].items()}
        target = TargetProfile(**data["target"])
        return Profile(vowel_templates=templates, target=target, source=data.get("source", "calibrated"))
    except (FileNotFoundError, KeyError, ValueError, TypeError, json.JSONDecodeError):
        return _builtin_profile()


def save(profile: Profile) -> None:
    """原子写 JSON(先写临时文件再 rename)。"""
    path = _profile_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(profile.to_dict(), f)
    os.replace(tmp, path)
