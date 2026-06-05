from dataclasses import dataclass
from typing import Optional


@dataclass
class TargetProfile:
    name: str
    f0_min: float
    f0_max: float
    resonance_min: float
    resonance_max: float
    source: str = "builtin"

    def contains(self, f0: Optional[float], resonance: Optional[float]) -> dict:
        f0_in = f0 is not None and self.f0_min <= f0 <= self.f0_max
        res_in = resonance is not None and self.resonance_min <= resonance <= self.resonance_max
        return {"f0_in": f0_in, "resonance_in": res_in, "in_target": f0_in and res_in}


def builtin_default() -> TargetProfile:
    """默认目标带。数值为起步默认,后续可调/可标定覆盖。
    - f0 165–220 Hz:目标基频区间。
    - resonance 0.15–0.7 八度:相对中性基线整体抬升的共振峰区间。"""
    return TargetProfile(
        name="Default",
        f0_min=165.0,
        f0_max=220.0,
        resonance_min=0.15,
        resonance_max=0.7,
        source="builtin",
    )
