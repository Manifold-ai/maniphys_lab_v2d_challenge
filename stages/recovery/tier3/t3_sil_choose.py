"""Accept an object-pose candidate only when silhouette scores tell it apart from current.

Contract RECOVERY-C001.
"""
import numpy as np

MIN_MEDIAN = 0.5
MIN_GAIN = 0.05
MIN_GAP = 0.05
# 0.70 - 0.65 is slightly under 0.05 in binary float. Minima are inclusive.
_SCORE_TOL = 1e-9


def _refuse(reason, med):
    return {"decision": "refuse", "name": None, "reason": reason, "median": med}


def choose_pose(candidates: dict[str, list[float]]) -> dict:
    if "current" not in candidates:
        return _refuse("no-current", {})
    if any(len(scores) == 0 for scores in candidates.values()):
        return _refuse("empty", {name: np.median(scores) for name, scores in candidates.items() if scores})
    alternatives = [name for name in candidates if name != "current"]
    if not alternatives:
        return _refuse("no-alternative", {})
    med = {name: np.median(scores) for name, scores in candidates.items()}
    current = med["current"]
    if current > max(med[name] for name in alternatives):
        return _refuse("current-best", med)
    best_name = max(alternatives, key=lambda name: med[name])
    best = med[best_name]
    if best < MIN_MEDIAN:
        return _refuse("below-gate", med)
    if best - current + _SCORE_TOL < MIN_GAIN:
        return _refuse("gain", med)
    others = [med[name] for name in alternatives if name != best_name]
    if others and best - max(others) + _SCORE_TOL < MIN_GAP:
        return _refuse("tie", med)
    return {"decision": "accept", "name": best_name, "reason": "accept", "median": med}


def right_multiply(poses: np.ndarray, rotation: np.ndarray) -> np.ndarray:
    r4 = np.eye(4)
    r4[:3, :3] = rotation
    out = poses @ r4
    out[:, :3, 3] = poses[:, :3, 3]
    return out
