"""Accept an object-pose candidate only when silhouette scores tell it apart from current."""
import numpy as np

MIN_MEDIAN = 0.5
MIN_GAIN = 0.05
MIN_GAP = 0.05


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
    if best - current < MIN_GAIN:
        return _refuse("gain", med)
    others = [med[name] for name in alternatives if name != best_name]
    if others and best - max(others) < MIN_GAP:
        return _refuse("tie", med)
    return {"decision": "accept", "name": best_name, "reason": "accept", "median": med}
